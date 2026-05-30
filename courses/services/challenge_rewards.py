"""XP + heart rules for the Challenge Engine.

Phase 1 shipped raw XP grants here. Phase 5 routes EVERY grant through
the XP ledger (`motivation.services.xp_ledger`) so:
  * Each grant has a source_type + source_id.
  * Double-clicks / refreshes / replays never double-credit.
  * The Summary breakdown reads back from the ledger.
"""
from __future__ import annotations

import logging

from django.conf import settings


logger = logging.getLogger(__name__)


# ----- XP -----
XP_CORRECT             = getattr(settings, "CHALLENGE_XP_CORRECT", 10)
XP_WRONG               = getattr(settings, "CHALLENGE_XP_WRONG", 0)
XP_COMPLETION_BONUS    = getattr(settings, "CHALLENGE_XP_COMPLETION_BONUS", 20)
XP_PERFECT_BONUS       = getattr(settings, "CHALLENGE_XP_PERFECT_BONUS", 10)
XP_LISTENING_CORRECT   = getattr(settings, "CHALLENGE_XP_LISTENING_CORRECT", 12)
XP_SPEAKING_PLACEHOLDER = getattr(settings, "CHALLENGE_XP_SPEAKING_PLACEHOLDER", 5)

# ----- Hearts -----
HEARTS_TOTAL = getattr(settings, "CHALLENGE_HEARTS_TOTAL", 5)


def xp_for_answer(*, question, is_correct: bool) -> int:
    """XP for a single card outcome.

    Speaking placeholders pay a small fixed amount on self-check.
    Listening-skill questions pay slightly more when correct.
    Everything else uses the base correct/wrong rule.
    """
    if not is_correct:
        return XP_WRONG
    qt = getattr(question, "question_type", "") or ""
    try:
        from courses.services import question_type_registry as registry
        spec = registry.get_spec(qt) or {}
    except Exception:
        spec = {}
    if spec.get("placeholder") and "speaking" in (spec.get("skill") or []):
        return XP_SPEAKING_PLACEHOLDER
    if "listening" in (spec.get("skill") or []):
        return XP_LISTENING_CORRECT
    return XP_CORRECT


def heart_loss_for_answer(*, is_correct: bool) -> bool:
    """Whether the student loses a heart on this answer."""
    return not is_correct


def xp_completion_bonus(*, perfect: bool) -> int:
    """Bonus XP when the Challenge ends successfully.

    `perfect=True` means zero wrong answers across the whole session.
    """
    return XP_COMPLETION_BONUS + (XP_PERFECT_BONUS if perfect else 0)


# ---------------------------------------------------------------------------
# Ledger-aware credit helpers.
# ---------------------------------------------------------------------------

def credit_answer_xp(user, *, amount: int, answer, session) -> int:
    """Credit XP for a single ChallengeAnswer. Returns the amount actually
    credited (0 if it was a duplicate, the answer was already paid)."""
    if amount <= 0:
        return 0
    try:
        from motivation.services import xp_ledger
        tx = xp_ledger.award_xp(
            user, amount,
            source_type="challenge_answer",
            source_id=answer.pk,
            reason=f"challenge:{session.pk}:q{answer.question_id}",
            metadata={
                "challenge_session": session.pk,
                "question_id":       answer.question_id,
                "question_type":     answer.question.question_type,
            },
        )
        return amount if tx else 0
    except Exception:
        logger.exception(
            "Answer XP grant failed (user=%s answer=%s)",
            getattr(user, "pk", None), getattr(answer, "pk", None),
        )
        return 0


def credit_completion_bonus(user, *, session) -> int:
    """Credit the static completion bonus (20 XP). Idempotent per session."""
    try:
        from motivation.services import xp_ledger
        tx = xp_ledger.award_xp(
            user, XP_COMPLETION_BONUS,
            source_type="challenge_completion",
            source_id=session.pk,
            reason=f"challenge:{session.pk}:completion",
            metadata={"challenge_session": session.pk},
        )
        return XP_COMPLETION_BONUS if tx else 0
    except Exception:
        logger.exception("Completion bonus failed (session=%s)", session.pk)
        return 0


def credit_perfect_bonus(user, *, session) -> int:
    """Credit the +10 perfect bonus (only when wrong_count==0). Idempotent."""
    if session.wrong_count != 0:
        return 0
    try:
        from motivation.services import xp_ledger
        tx = xp_ledger.award_xp(
            user, XP_PERFECT_BONUS,
            source_type="perfect_bonus",
            source_id=session.pk,
            reason=f"challenge:{session.pk}:perfect",
            metadata={"challenge_session": session.pk},
        )
        return XP_PERFECT_BONUS if tx else 0
    except Exception:
        logger.exception("Perfect bonus failed (session=%s)", session.pk)
        return 0


# ---------------------------------------------------------------------------
# Back-compat shim — kept so old call sites (legacy challenge_runner code,
# tests) still link. New code should call the ledger-aware helpers above.
# ---------------------------------------------------------------------------

def credit_user_xp(user, amount: int, *, reason: str) -> None:
    """Deprecated — use credit_answer_xp / credit_completion_bonus /
    credit_perfect_bonus. Kept as a no-op tunnel through `xp_service.award_xp`
    so any forgotten caller still adds to the aggregate."""
    if amount <= 0:
        return
    try:
        from motivation.services.xp_service import award_xp
        award_xp(user, amount, reason=reason)
    except Exception:
        logger.exception(
            "Challenge XP grant failed (user=%s amount=%s reason=%s)",
            getattr(user, "pk", None), amount, reason,
        )
