"""Strict-but-safe placement completion gate.

The final result + course assignment require a COMPLETED speaking section,
not just the written section. A too-short / empty / failed speaking call is
retryable and never finalises placement. Configurable via:
  * PLACEMENT_REQUIRE_SPEAKING_FOR_FINAL_RESULT (default True)
  * PLACEMENT_SPEAKING_MIN_ANSWERS (default 3)
"""
from __future__ import annotations

from django.conf import settings


def require_speaking() -> bool:
    return bool(getattr(settings, "PLACEMENT_REQUIRE_SPEAKING_FOR_FINAL_RESULT", True))


def min_answers() -> int:
    return int(getattr(settings, "PLACEMENT_SPEAKING_MIN_ANSWERS", 3))


def max_retries() -> int:
    return int(getattr(settings, "PLACEMENT_SPEAKING_MAX_RETRIES", 3))


def count_questions_asked(conv) -> int:
    """How many questions the tutor actually asked (assistant turns with '?').

    Used to tell a 'tutor asked everything but the student couldn't answer'
    call (→ unable_to_answer) apart from a call that dropped early (→ retry).
    """
    if conv is None:
        return 0
    from tutor.models import TutorMessage
    rows = TutorMessage.objects.filter(conversation=conv, role="assistant").values_list("content", flat=True)
    return sum(1 for c in rows if "?" in (c or ""))


def count_speaking_answers(attempt) -> int:
    """Number of speaking questions with a non-empty captured transcript."""
    return (
        attempt.questions.filter(section="speaking")
        .exclude(transcript="").exclude(transcript__isnull=True)
        .count()
    )


def speaking_is_complete(attempt, *, eval_obj=None) -> bool:
    """True when the speaking section is rich enough to finalise.

    Requires a VoiceCallEvaluation (the STT/scoring succeeded) AND at least
    ``min_answers()`` captured answers.
    """
    if eval_obj is None:
        from tutor.models import VoiceCallEvaluation
        conv = attempt.voice_conversation
        eval_obj = (
            VoiceCallEvaluation.objects.filter(conversation=conv).first()
            if conv is not None else None
        )
    if eval_obj is None:
        return False
    return count_speaking_answers(attempt) >= min_answers()


def is_finalised(attempt) -> bool:
    """A placement is finalised only when completed AND a result row exists."""
    return attempt.status == "completed" and attempt.result_id is not None
