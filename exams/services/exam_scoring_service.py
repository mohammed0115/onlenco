"""Score an `ExamAttempt` and feed wrong answers back into the adaptive
loop (UserError → UserWeakness → SkillMastery → theta)."""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from learning_core.models import ExerciseAttempt, UserError
from learning_core.services.adaptive_difficulty import process_attempt
from learning_core.services.weakness_engine import update_user_weaknesses

from ..models import ExamAnswer, ExamAttempt

logger = logging.getLogger(__name__)

# Question types where the user produces their own text — these get
# routed through the rich error analyser. MCQ-style answers go through
# the direct UserError path because there's no prose to NLP-analyse.
_FREE_TEXT_QTYPES = {
    "writing_prompt", "speaking_prompt", "short_answer",
    "translation", "grammar_transformation", "correction",
}


def _is_correct(question, user_answer: str) -> bool:
    expected = (question.correct_answer or "").strip().lower()
    candidate = (user_answer or "").strip().lower()
    if not expected or not candidate:
        return False
    if candidate == expected:
        return True
    # Honour acceptable_answers list when provided.
    extras = question.acceptable_answers or []
    if isinstance(extras, list):
        return any(candidate == str(a).strip().lower() for a in extras)
    return False


def submit_answer(attempt: ExamAttempt, question, user_answer: str) -> ExamAnswer:
    """Persist a single answer + propagate it into the adaptive loop."""
    correct = _is_correct(question, user_answer)
    score = (question.points or 1) if correct else 0
    feedback = (
        question.feedback_correct if correct else question.feedback_wrong
    ) or (question.explanation or "")
    with transaction.atomic():
        ans, _ = ExamAnswer.objects.update_or_create(
            attempt=attempt, question=question,
            defaults={
                "user_answer": user_answer or "",
                "is_correct": correct,
                "score": score,
                "feedback": feedback,
            },
        )
        # Mirror as an ExerciseAttempt so all downstream adaptive
        # services (theta, mastery, weaknesses, motivation) see it.
        try:
            ex_attempt = ExerciseAttempt.objects.create(
                user=attempt.user, exercise=question,
                user_answer=user_answer or "",
                is_correct=correct,
                score=1.0 if correct else 0.0,
                metadata={"exam_attempt_id": attempt.id},
            )
            process_attempt(attempt.user, question, ex_attempt)
        except Exception as e:
            logger.warning("scoring: process_attempt failed: %s", e)

        # Wrong answer → feed the adaptive error pipeline.
        # Free-text answers go through analyze_text() so the user gets
        # structured grammar/spelling/lexical error tagging. MCQ-style
        # answers fall back to a direct UserError row because there's
        # no prose for the analyser to chew on.
        if not correct:
            qtype = question.question_type or ""
            text_in = (user_answer or "").strip()
            if qtype in _FREE_TEXT_QTYPES and text_in:
                try:
                    from learning_core.services.error_analyzer import analyze_text
                    ans.error_analysis = analyze_text(
                        attempt.user,
                        text_in,
                        source_type="quiz",
                        context={
                            "cefr_level": question.cefr_level or "",
                            "skill": getattr(question.skill, "category", "") or "",
                            "expected": question.correct_answer or "",
                        },
                    ) or {}
                    ans.save(update_fields=["error_analysis"])
                except Exception as e:
                    logger.warning("scoring: analyze_text failed: %s", e)
            else:
                try:
                    UserError.objects.create(
                        user=attempt.user,
                        source_type="quiz",
                        original_text=text_in,
                        corrected_text=question.correct_answer or "",
                        error_type="grammar",
                        skill=question.skill,
                        severity=5,
                        explanation=question.explanation or "",
                        ai_confidence=0.0,
                        metadata={
                            "exam_attempt_id": attempt.id,
                            "question_id": question.id,
                        },
                    )
                except Exception as e:
                    logger.warning("scoring: UserError create failed: %s", e)
    return ans


def finalise_attempt(attempt: ExamAttempt) -> ExamAttempt:
    """Compute totals + percentage + pass/fail; flip status to graded.
    Recomputes weaknesses + fires the motivation engine for the user."""
    answers = list(attempt.answers.select_related("question"))
    total_points = sum((a.question.points or 1) for a in answers) or 1
    earned = sum((a.score or 0) for a in answers)
    pct = (earned / total_points) * 100.0
    passed = pct >= ((attempt.exam.blueprint.passing_score if attempt.exam.blueprint else 70))

    attempt.score = earned
    attempt.percentage = round(pct, 2)
    attempt.passed = passed
    attempt.status = "graded"
    attempt.submitted_at = attempt.submitted_at or timezone.now()
    attempt.save(update_fields=[
        "score", "percentage", "passed", "status", "submitted_at",
    ])

    # Recompute weaknesses + motivation engine in the same hot path so
    # the dashboard reflects the result immediately.
    try:
        update_user_weaknesses(attempt.user)
    except Exception:
        logger.exception("scoring: weakness recompute failed")
    try:
        from motivation.services.motivation_engine import run_for_user
        run_for_user(attempt.user)
    except Exception:
        logger.exception("scoring: motivation engine failed")
    return attempt


def grade_attempt(attempt: ExamAttempt, answers: Iterable[dict]) -> ExamAttempt:
    """Bulk-grade an attempt from an iterable of `{question_id, user_answer}`
    dicts. Convenience wrapper used by the API submit endpoint."""
    by_id: dict[int, object] = {
        eq.question_id: eq.question
        for eq in attempt.exam.questions.all().select_related("question")
    }
    for entry in answers:
        qid = entry.get("question_id") or entry.get("id")
        ans = entry.get("user_answer") or entry.get("answer") or ""
        q = by_id.get(int(qid)) if qid else None
        if q is None:
            continue
        submit_answer(attempt, q, ans)
    return finalise_attempt(attempt)
