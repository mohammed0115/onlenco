"""Grade a ChallengeAnswer by dispatching through the registry.

Phase 3: every type that the registry knows about gets graded by its
configured `grader` (see `question_graders.GRADERS`). Unknown types
return a soft "not gradable yet" result so the Challenge never 500s.
"""
from __future__ import annotations

from typing import Any

from courses.models import LessonQuestion
from courses.services import question_graders, question_type_registry as registry


def grade(question: LessonQuestion, raw_response: Any) -> dict:
    """Return the standard grader dict.

    Keys:
      is_correct (bool)
      score      (float in [0, 1])
      feedback_en (str)
      feedback_ar (str)
    """
    if not registry.is_known(question.question_type):
        return {
            "is_correct": False,
            "score": 0.0,
            "feedback_en": (
                f"'{question.question_type}' isn't in the registry — "
                "the card was shown but not scored."
            ),
            "feedback_ar": (
                "هذا النوع غير موجود في السجل — ظهر السؤال لكنه لم يُصحَّح."
            ),
            "_unsupported": True,
        }
    result = question_graders.grade(question, raw_response)
    # Normalise — every grader is expected to return all four keys, but
    # backstop defensively.
    result.setdefault("score", 1.0 if result.get("is_correct") else 0.0)
    result.setdefault("feedback_en", "")
    result.setdefault("feedback_ar", "")
    return result
