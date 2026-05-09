"""XP awarding + leveling.

Computes XP earned during a snapshot and credits it to UserXP. Resets
weekly/monthly buckets at the right cadence.
"""
from __future__ import annotations

from datetime import date as _date, timedelta
from typing import Tuple

from django.db import transaction
from django.utils import timezone

from .. import constants as C
from ..models import LearnerActivitySnapshot, UserXP


def _xp_for_snapshot(snap: LearnerActivitySnapshot) -> Tuple[int, dict]:
    """Compute XP earned today and a dict of the components for traceability."""
    breakdown = {}
    total = 0

    if snap.lessons_completed:
        v = snap.lessons_completed * C.XP_LESSON_COMPLETE
        breakdown["lessons"] = v
        total += v

    if snap.quizzes_completed:
        v = snap.quizzes_completed * C.XP_QUIZ_COMPLETE
        breakdown["quizzes"] = v
        total += v

    if snap.questions_answered >= 20 and snap.quiz_accuracy >= 85.0:
        breakdown["quiz_high_accuracy"] = C.XP_QUIZ_HIGH_ACCURACY
        total += C.XP_QUIZ_HIGH_ACCURACY

    if snap.speaking_minutes >= 10:
        v = (snap.speaking_minutes // 10) * C.XP_SPEAKING_10_MIN
        breakdown["speaking"] = v
        total += v

    if snap.ai_chat_minutes >= 20:
        v = (snap.ai_chat_minutes // 20) * C.XP_AI_CHAT_20_MIN
        breakdown["ai_chat"] = v
        total += v

    if snap.words_read >= 500:
        v = (snap.words_read // 500) * C.XP_READ_500_WORDS
        breakdown["reading"] = v
        total += v

    if snap.weekly_assessments_completed:
        v = snap.weekly_assessments_completed * C.XP_WEEKLY_ASSESSMENT
        breakdown["weekly_assessment"] = v
        total += v

    if snap.current_streak_days and snap.current_streak_days >= 1:
        breakdown["daily_streak"] = C.XP_DAILY_STREAK
        total += C.XP_DAILY_STREAK

    if snap.mastery_delta and snap.mastery_delta >= 0.25:
        breakdown["level_improved"] = C.XP_LEVEL_IMPROVED
        total += C.XP_LEVEL_IMPROVED

    return total, breakdown


def _ensure_buckets(xp: UserXP, today: _date) -> None:
    """Reset weekly bucket on Monday-rollover and monthly bucket on month-rollover."""
    changed = False
    monday = today - timedelta(days=today.weekday())
    if not xp.weekly_xp_reset_at or xp.weekly_xp_reset_at < monday:
        xp.weekly_xp = 0
        xp.weekly_xp_reset_at = monday
        changed = True
    first_of_month = today.replace(day=1)
    if not xp.monthly_xp_reset_at or xp.monthly_xp_reset_at < first_of_month:
        xp.monthly_xp = 0
        xp.monthly_xp_reset_at = first_of_month
        changed = True
    if changed:
        xp.save(update_fields=["weekly_xp", "weekly_xp_reset_at", "monthly_xp", "monthly_xp_reset_at"])


def award_xp(user, amount: int, *, reason: str = "") -> UserXP:
    """Add `amount` XP to user's totals (atomic). Returns updated UserXP."""
    if amount <= 0:
        xp, _ = UserXP.objects.get_or_create(user=user)
        return xp
    with transaction.atomic():
        xp, _ = UserXP.objects.select_for_update().get_or_create(user=user)
        _ensure_buckets(xp, timezone.localdate())
        xp.total_xp = (xp.total_xp or 0) + amount
        xp.weekly_xp = (xp.weekly_xp or 0) + amount
        xp.monthly_xp = (xp.monthly_xp or 0) + amount
        xp.level_number = max(1, (xp.total_xp // C.XP_PER_LEVEL) + 1)
        xp.save()
    return xp


def award_for_snapshot(snap: LearnerActivitySnapshot) -> Tuple[int, dict, UserXP]:
    """Compute and award XP for a snapshot. Idempotent via metadata['xp_awarded']."""
    if snap.metadata.get("xp_awarded"):
        xp, _ = UserXP.objects.get_or_create(user=snap.user)
        return 0, snap.metadata.get("xp_breakdown", {}), xp

    total, breakdown = _xp_for_snapshot(snap)
    xp = award_xp(snap.user, total, reason=f"snapshot {snap.date}")

    snap.metadata["xp_awarded"] = total
    snap.metadata["xp_breakdown"] = breakdown
    snap.save(update_fields=["metadata"])
    return total, breakdown, xp
