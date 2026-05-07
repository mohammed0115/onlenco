"""Adapter from a lesson quiz submission to the adaptive learning loop.

Called from `lessons.views.quiz_attempt` AFTER the legacy LessonProgress
update has succeeded. Designed to be fully optional: any failure here is
swallowed and logged — the student's quiz response must never break.

For each Question:
  - find-or-create an AdaptiveExercise that mirrors the question
  - create an ExerciseAttempt
  - update theta + skill mastery
For each WRONG Question:
  - create a UserError (source_type="quiz")
After the batch:
  - run weakness_engine.update_user_weaknesses
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction

from learning_core.models import AdaptiveExercise, ExerciseAttempt, Skill, UserError
from learning_core.services.adaptive_difficulty import process_attempt
from learning_core.services.weakness_engine import update_user_weaknesses
from lessons.models import Question

logger = logging.getLogger(__name__)


def _resolve_skill(category_value: str | None) -> Skill | None:
    if not category_value:
        return None
    return Skill.objects.filter(category=category_value, is_active=True).first()


def _get_or_create_mirror(question: Question, skill: Skill | None) -> AdaptiveExercise:
    """One AdaptiveExercise row per lessons.Question, linked via metadata."""
    metadata_key = f"lesson_question:{question.id}"
    existing = AdaptiveExercise.objects.filter(
        metadata__source_key=metadata_key
    ).first()
    if existing:
        return existing

    options = [
        question.choice_a,
        question.choice_b,
        question.choice_c,
        question.choice_d,
    ]
    options = [o for o in options if o]
    return AdaptiveExercise.objects.create(
        skill=skill,
        cefr_level=question.quiz.lesson.level,
        difficulty_score=0.5,
        question_type="multiple_choice",
        question=question.prompt,
        options=options,
        correct_answer=question.correct,
        explanation="",
        generated_by_ai=False,
        metadata={
            "source_key": metadata_key,
            "source": "lesson_quiz_mirror",
            "lesson_id": question.quiz.lesson_id,
            "quiz_id": question.quiz_id,
            "question_id": question.id,
        },
    )


def process_quiz_submission(user, lesson, question_results: Iterable[dict]) -> dict:
    """Apply adaptive learning side-effects from a graded quiz.

    `question_results` is an iterable of dicts with keys:
        q (lessons.models.Question), chosen (str), correct (str)
    """
    summary = {
        "errors_created": 0,
        "attempts_recorded": 0,
        "weaknesses_recomputed": False,
    }
    skill = _resolve_skill(lesson.skill)

    try:
        with transaction.atomic():
            for r in question_results:
                question: Question = r["q"]
                chosen = (r.get("chosen") or "").strip().lower()
                is_correct = chosen == r["correct"]
                exercise = _get_or_create_mirror(question, skill)
                attempt = ExerciseAttempt.objects.create(
                    user=user,
                    exercise=exercise,
                    user_answer=chosen,
                    is_correct=is_correct,
                    score=1.0 if is_correct else 0.0,
                    metadata={"lesson_id": lesson.id, "question_id": question.id},
                )
                summary["attempts_recorded"] += 1

                # Theta + mastery update
                try:
                    process_attempt(user, exercise, attempt)
                except Exception as e:
                    logger.warning("adaptive_quiz_adapter: theta update failed: %s", e)

                # UserError for wrong answers
                if not is_correct:
                    UserError.objects.create(
                        user=user,
                        source_type="quiz",
                        original_text=chosen,
                        corrected_text=r["correct"],
                        error_type="grammar",
                        skill=skill,
                        severity=5,
                        explanation=f"Selected '{chosen}', expected '{r['correct']}'.",
                        ai_confidence=0.0,
                        metadata={
                            "lesson_id": lesson.id,
                            "question_id": question.id,
                        },
                    )
                    summary["errors_created"] += 1

        # Weakness recompute is OK to do outside the transaction.
        if summary["errors_created"]:
            try:
                update_user_weaknesses(user)
                summary["weaknesses_recomputed"] = True
            except Exception as e:
                logger.warning("adaptive_quiz_adapter: weakness update failed: %s", e)

        # Trigger weekly assessment if lesson count threshold reached
        try:
            from learning_core.services.weekly_assessment import maybe_trigger
            wa = maybe_trigger(user)
            if wa is not None:
                summary["weekly_assessment_triggered"] = wa.id
        except Exception as e:
            logger.warning("adaptive_quiz_adapter: weekly trigger failed: %s", e)

        # Notify student of lesson completion (best-effort).
        try:
            from lessons.models import LessonProgress
            progress = LessonProgress.objects.filter(user=user, lesson=lesson).first()
            if progress and progress.completed_at:
                from notifications import constants as C
                from notifications.services import NotificationService
                NotificationService().trigger(
                    C.LESSON_COMPLETED,
                    user=user,
                    payload={
                        "lesson_title": lesson.title,
                        "score": progress.quiz_score,
                        "cta_url": "/dashboard/",
                        "cta_label": "Continue learning",
                        "dedup_key": f"lesson:{lesson.id}",
                    },
                )
        except Exception as e:
            logger.warning("adaptive_quiz_adapter: lesson_completed notify failed: %s", e)

    except Exception as e:
        logger.exception("adaptive_quiz_adapter: aborted: %s", e)

    return summary
