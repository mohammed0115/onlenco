"""Phase 6 — Mastery + Mistake update pipeline.

Single public entry: `process_challenge_answer(answer)`. Everything
else is internal.

Idempotency: a MasteryEvent row keyed on `challenge_answer` is created
BEFORE any updates. A second call for the same answer hits the OneToOne
constraint, raises IntegrityError, and we return early with no work
done. This is the canonical guard — neither refresh nor duplicate submit
can re-credit mastery / re-schedule reviews / re-tag mistakes.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import (
    MasteryEvent, SkillMastery, StudentMistake,
    confidence_for,
)
from . import mistake_classifier, review_scheduler, skill_resolver


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Score tuning (Phase 6 spec).
# ---------------------------------------------------------------------------

# Easy / medium / hard increments on correct + decrements on wrong.
# Difficulty comes from `LessonQuestion.difficulty_score` (0..1 in the
# model) — we band it: 0..0.33 easy, 0.34..0.66 medium, 0.67..1 hard.
DELTA_TABLE = {
    "easy":   {"correct": +5,  "wrong": -8},
    "medium": {"correct": +8,  "wrong": -6},
    "hard":   {"correct": +12, "wrong": -4},
}


def _band_difficulty(question) -> str:
    d = float(getattr(question, "difficulty_score", 0.5) or 0.5)
    if d <= 0.33:
        return "easy"
    if d <= 0.66:
        return "medium"
    return "hard"


def _apply_score_delta(current: float, delta: float, *, partial: float | None = None) -> float:
    """Apply delta, optionally scaled by a 0..1 partial-credit factor."""
    if partial is not None:
        delta *= float(partial)
    new = (current or 0.0) + delta
    return max(0.0, min(100.0, new))


# ---------------------------------------------------------------------------
# Public entry — called by challenge_runner after each ChallengeAnswer.
# ---------------------------------------------------------------------------

def process_challenge_answer(answer) -> bool:
    """Update mastery + mistakes for `answer`.

    Returns True if work was done, False if this answer was already
    processed (idempotent no-op).
    """
    if answer is None:
        return False
    try:
        with transaction.atomic():
            event = MasteryEvent.objects.create(
                user=answer.session.user,
                challenge_answer=answer,
                metadata={"is_correct": bool(answer.is_correct)},
            )
    except IntegrityError:
        # Already processed — refresh/dup submit guard.
        return False

    try:
        with transaction.atomic():
            _update_mastery(answer)
            _update_mistake(answer)
    except Exception:
        # Don't propagate — the Challenge engine must finish. Mark the
        # event so we know we tried.
        logger.exception(
            "Mastery processing failed (answer pk=%s)", answer.pk,
        )
        event.metadata["error"] = "see logs"
        event.save(update_fields=["metadata"])
    return True


# ---------------------------------------------------------------------------
# Mastery update.
# ---------------------------------------------------------------------------

def _update_mastery(answer) -> None:
    user = answer.session.user
    question = answer.question
    skills = skill_resolver.get_question_skills(question)
    if not skills:
        return
    band = _band_difficulty(question)
    deltas = DELTA_TABLE[band]
    is_correct = bool(answer.is_correct)
    score = float(answer.score or 0.0)
    # Partial credit on match_pairs etc. dampens delta proportionally.
    partial = score if (0.0 < score < 1.0) else None
    delta = deltas["correct"] if is_correct else deltas["wrong"]

    for skill in skills:
        mastery, _ = SkillMastery.objects.select_for_update().get_or_create(
            user=user, skill=skill,
        )
        mastery.mastery_score = _apply_score_delta(
            mastery.mastery_score, delta, partial=partial,
        )
        mastery.attempts_count = (mastery.attempts_count or 0) + 1
        if is_correct:
            mastery.correct_count = (mastery.correct_count or 0) + 1
            mastery.current_streak_correct = (mastery.current_streak_correct or 0) + 1
            mastery.current_streak_wrong = 0
        else:
            mastery.wrong_count = (mastery.wrong_count or 0) + 1
            mastery.current_streak_wrong = (mastery.current_streak_wrong or 0) + 1
            mastery.current_streak_correct = 0
        mastery.confidence_level = confidence_for(mastery.mastery_score)
        mastery.last_practiced_at = timezone.now()
        mastery.save()


# ---------------------------------------------------------------------------
# Mistake update.
# ---------------------------------------------------------------------------

def _update_mistake(answer) -> None:
    user = answer.session.user
    question = answer.question
    is_correct = bool(answer.is_correct)

    if is_correct:
        _maybe_mark_existing_mistake_improved(user, question)
        return

    # Wrong answer — UPSERT a StudentMistake row.
    mistake_type, severity = mistake_classifier.classify(question)
    primary_skill = skill_resolver.get_primary_skill(question)
    lesson = getattr(getattr(answer.session, "lesson", None), "pk", None)
    from courses.models import Lesson
    lesson_obj = answer.session.lesson if hasattr(answer.session, "lesson") else None

    defaults = dict(
        lesson=lesson_obj,
        skill=primary_skill,
        challenge_answer=answer,
        mistake_type=mistake_type,
        severity=severity,
        user_answer=str(answer.user_answer or "")[:1000],
        correct_answer=str(question.correct_answer or ""),
        explanation_en=answer.feedback_en or "",
        explanation_ar=answer.feedback_ar or "",
    )
    mistake, was_new = StudentMistake.objects.get_or_create(
        user=user, question=question, defaults=defaults,
    )
    if not was_new:
        # Refresh fields that may have changed + bump the review count.
        mistake.lesson = lesson_obj or mistake.lesson
        mistake.skill = primary_skill or mistake.skill
        mistake.challenge_answer = answer
        mistake.mistake_type = mistake_type
        mistake.severity = severity
        mistake.user_answer = str(answer.user_answer or "")[:1000]
        mistake.review_count = (mistake.review_count or 0) + 1
        mistake.mastered = False
    review_scheduler.schedule_mistake_review(mistake)
    mistake.save()


def _maybe_mark_existing_mistake_improved(user, question) -> None:
    """Correct follow-up on a question that has a mistake row →
    push out the review schedule (or mark mastered)."""
    mistake = StudentMistake.objects.filter(
        user=user, question=question, mastered=False,
    ).first()
    if mistake is None:
        return
    primary_skill = mistake.skill or skill_resolver.get_primary_skill(question)
    if primary_skill is None:
        # No skill linkage — just bump it out a day.
        from datetime import timedelta
        mistake.next_review_at = timezone.now() + timedelta(days=1)
        mistake.save(update_fields=["next_review_at", "updated_at"])
        return
    mastery = SkillMastery.objects.filter(
        user=user, skill=primary_skill,
    ).first()
    score = mastery.mastery_score if mastery else 0.0
    review_scheduler.mark_mistake_improved(mistake, mastery_score=score)
    mistake.save()


def record_manual_review(mistake, *, correct: bool) -> None:
    """Update a mistake's spaced-repetition schedule from a manual review card.

    Used by the student-facing "Review mistakes" page (recall cards). Three
    clean recalls mark the mistake mastered; a wrong recall brings it back
    soon. Self-contained so the review UI doesn't depend on session state.
    """
    from datetime import timedelta
    now = timezone.now()
    mistake.review_count = (mistake.review_count or 0) + 1
    if correct:
        if mistake.review_count >= 3:
            mistake.mastered = True
            mistake.next_review_at = now + timedelta(days=7)
        else:
            mistake.next_review_at = now + timedelta(days=1 if mistake.review_count == 1 else 3)
    else:
        mistake.mastered = False
        mistake.next_review_at = now + timedelta(hours=4)
    mistake.save(update_fields=["review_count", "mastered", "next_review_at", "updated_at"])


# ---------------------------------------------------------------------------
# Convenience: per-session breakdown for the Summary view.
# ---------------------------------------------------------------------------

def skills_practiced_in_session(session) -> list[dict]:
    """Return `[{skill, attempts, correct, mastery_score, delta_hint}, ...]`
    for the skills practiced during this Challenge session — used by the
    Summary 'Skills practiced' tile."""
    from ..models import SkillMastery
    user = session.user
    answers = session.answers.select_related("question")
    skill_counts: dict[int, dict] = {}
    for ans in answers:
        skills = skill_resolver.get_question_skills(ans.question)
        for s in skills:
            entry = skill_counts.setdefault(s.pk, {
                "skill": s, "attempts": 0, "correct": 0,
            })
            entry["attempts"] += 1
            if ans.is_correct:
                entry["correct"] += 1

    # Attach current mastery scores.
    mastery_by_skill = {
        m.skill_id: m
        for m in SkillMastery.objects.filter(
            user=user, skill_id__in=list(skill_counts.keys()),
        )
    }
    out = []
    for skill_id, entry in skill_counts.items():
        mastery = mastery_by_skill.get(skill_id)
        out.append({
            "skill":          entry["skill"],
            "attempts":       entry["attempts"],
            "correct":        entry["correct"],
            "mastery_score":  getattr(mastery, "mastery_score", None),
            "confidence":     getattr(mastery, "confidence_level", "new"),
        })
    # Sort by attempts desc (most-practiced first).
    out.sort(key=lambda e: -e["attempts"])
    return out
