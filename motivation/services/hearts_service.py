"""Hearts policy — Phase 5.

Hearts are per-ChallengeSession (no global wallet yet). This module
centralises every decision the runner needs to make about them so the
rules are tunable in one place.

Public API:
  * get_default_hearts(user)   — how many hearts a fresh session starts with
  * apply_wrong_answer(session) — decrement and persist; returns True if a heart was actually lost
  * can_continue(session)       — False once hearts hit 0
  * reset_hearts_for_retry(session) — bumps to default (Phase 6 may track refills)
  * get_hearts_display(session) — { remaining, total, lost, low }

TODO Phase 6:
  * Global Heart wallet across sessions.
  * Time-based refill (e.g. +1 heart every 4 hours).
  * Optional XP-to-heart trade.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings


if TYPE_CHECKING:
    from courses.models import ChallengeSession


DEFAULT_HEARTS = getattr(settings, "MOTIVATION_DEFAULT_HEARTS", 5)
LOW_HEART_THRESHOLD = getattr(settings, "MOTIVATION_LOW_HEART_THRESHOLD", 1)


def get_default_hearts(user) -> int:
    """Hearts the next Challenge starts with. Constant for now —
    Phase 6 may scale by user tier or subscription."""
    return DEFAULT_HEARTS


def apply_wrong_answer(session: "ChallengeSession") -> bool:
    """Decrement hearts on a wrong answer (if any are left). Returns
    True if a heart was actually subtracted, False on the no-heart-to-lose
    edge case."""
    if not session.is_active:
        return False
    if (session.hearts_remaining or 0) <= 0:
        return False
    session.hearts_remaining -= 1
    session.save(update_fields=["hearts_remaining", "updated_at"])
    return True


def can_continue(session: "ChallengeSession") -> bool:
    return (session.hearts_remaining or 0) > 0


def reset_hearts_for_retry(session: "ChallengeSession") -> None:
    """Refill hearts when the student starts a retry session.
    Phase 5 ships unlimited retries — no refill ledger yet."""
    session.hearts_remaining = session.hearts_total or DEFAULT_HEARTS
    session.save(update_fields=["hearts_remaining", "updated_at"])


def get_hearts_display(session: "ChallengeSession") -> dict:
    remaining = session.hearts_remaining or 0
    total = session.hearts_total or DEFAULT_HEARTS
    return {
        "remaining": remaining,
        "total":     total,
        "lost":      max(0, total - remaining),
        "low":       remaining <= LOW_HEART_THRESHOLD,
        "depleted":  remaining == 0,
    }
