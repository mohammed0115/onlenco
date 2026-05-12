"""Post-quiz side effects for courses-app lesson quizzes.

Mirrors `lessons.services.adaptive_quiz_adapter.process_quiz_submission`
for the parallel courses-app schema (`LessonQuiz`, `LessonQuestion`).
Writes UserError rows for wrong answers, recomputes weaknesses, fires
the motivation engine, and generates a small batch of personalised
AdaptiveExercises so the student can immediately drill the weak spot.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction

logger = logging.getLogger(__name__)


def process_course_quiz_submission(
    user, lesson, question_results: Iterable[dict]
) -> dict:
    """Apply adaptive side-effects from a graded courses-app quiz.

    `question_results` is an iterable of dicts:
        {q: LessonQuestion, chosen: str, correct: str, is_correct: bool}
    """
    summary = {
        "errors_created": 0,
        "weaknesses_recomputed": False,
        "personalised_exercises": [],
    }

    try:
        from learning_core.models import UserError
    except Exception:
        return summary

    try:
        with transaction.atomic():
            for r in question_results:
                if r.get("is_correct"):
                    continue
                question = r["q"]
                UserError.objects.create(
                    user=user,
                    source_type="quiz",
                    original_text=(r.get("chosen") or "")[:1000],
                    corrected_text=(r.get("correct") or "")[:1000],
                    error_type="grammar",
                    severity=5,
                    explanation=(question.explanation or "")[:1000],
                    ai_confidence=0.0,
                    metadata={
                        "course_lesson_id": lesson.id,
                        "lesson_question_id": question.id,
                    },
                )
                summary["errors_created"] += 1

        if summary["errors_created"]:
            try:
                from learning_core.services.weakness_engine import update_user_weaknesses
                update_user_weaknesses(user)
                summary["weaknesses_recomputed"] = True
            except Exception:
                logger.warning("course quiz: weakness recompute failed", exc_info=True)

        try:
            exercises = _generate_personalised_exercises(user)
            summary["personalised_exercises"] = exercises
        except Exception:
            logger.warning("course quiz: personalised exercise gen failed",
                           exc_info=True)

        try:
            from motivation.services.motivation_engine import run_for_user
            run_for_user(user)
        except Exception:
            logger.warning("course quiz: motivation engine failed", exc_info=True)
    except Exception:
        logger.exception("process_course_quiz_submission aborted")

    return summary


def _generate_personalised_exercises(user, *, count_per_weakness: int = 2) -> list:
    """Generate a small batch (default 2 per weakness) and return them.

    Returns plain dicts so the calling template can render without
    needing learning_core imports.
    """
    try:
        from learning_core.services.exercise_generator import generate_personalized_exercises
    except Exception:
        return []
    try:
        exercises = generate_personalized_exercises(
            user, count_per_weakness=count_per_weakness,
        )
    except Exception:
        logger.exception("generate_personalized_exercises raised")
        return []
    out = []
    for ex in (exercises or [])[:3]:
        out.append({
            "id": ex.id,
            "question": ex.question,
            "cefr_level": ex.cefr_level,
            "options": list(ex.options or []),
            "question_type": ex.question_type,
        })
    return out
