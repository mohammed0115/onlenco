"""Daily-goal tracking — Phase 5.

One per-user XP goal (default 50 XP/day). Progress increments whenever
the student earns XP. When today's progress crosses the target, we:

  1. Mark the row `completed=True`.
  2. Credit a one-shot bonus (default 25 XP) via the XP ledger so the
     bonus itself shows up in the Summary breakdown.
  3. Record a `daily_goal_completed` streak activity.

All steps are idempotent — calling `update_daily_goal_progress` twice
for the same XP delta is safe-ish (the same XP would be tracked twice
if the caller bugs out, but the bonus + streak activity are guarded by
`bonus_awarded` and the StreakActivity unique-constraint).
"""
from __future__ import annotations

from datetime import date as _date
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import DailyGoal, DailyGoalProgress


DEFAULT_TARGET_XP = getattr(settings, "MOTIVATION_DAILY_GOAL_XP", 50)
DAILY_GOAL_BONUS_XP = getattr(settings, "MOTIVATION_DAILY_GOAL_BONUS_XP", 25)


def get_or_create_daily_goal(user) -> DailyGoal:
    goal, _ = DailyGoal.objects.get_or_create(
        user=user,
        defaults={"goal_type": "xp", "target_value": DEFAULT_TARGET_XP},
    )
    return goal


def _get_or_create_progress(user, on_date: _date) -> DailyGoalProgress:
    progress, _ = DailyGoalProgress.objects.get_or_create(
        user=user, date=on_date,
    )
    return progress


@transaction.atomic
def update_daily_goal_progress(
    user,
    xp_amount: int,
    *,
    on_date: Optional[_date] = None,
    challenges_delta: int = 0,
    minutes_delta: int = 0,
) -> tuple[DailyGoalProgress, bool, int]:
    """Increment today's progress and return:
        (progress_row, just_completed?, bonus_xp_awarded)

    `just_completed=True` means this call is the one that crossed the
    target — callers may want to fire encouragement messages on it.
    """
    when = on_date or timezone.localdate()
    goal = get_or_create_daily_goal(user)
    progress = (
        DailyGoalProgress.objects
        .select_for_update()
        .get_or_create(user=user, date=when)[0]
    )

    if xp_amount > 0:
        progress.xp_earned = (progress.xp_earned or 0) + int(xp_amount)
    if challenges_delta:
        progress.challenges_completed = (progress.challenges_completed or 0) + int(challenges_delta)
    if minutes_delta:
        progress.minutes_spent = (progress.minutes_spent or 0) + int(minutes_delta)

    target = goal.target_value or DEFAULT_TARGET_XP
    just_completed = False
    bonus_awarded = 0

    if not progress.completed and progress.xp_earned >= target:
        progress.completed = True
        progress.completed_at = timezone.now()
        just_completed = True

    progress.save()

    # One-shot bonus + streak activity. Done OUTSIDE the conditional so
    # a row that became completed=True earlier (e.g. through a manual
    # backfill) can still get its bonus on the NEXT XP credit if it
    # didn't get one the first time.
    if progress.completed and not progress.bonus_awarded:
        from . import xp_ledger
        tx = xp_ledger.award_xp(
            user, DAILY_GOAL_BONUS_XP,
            source_type="daily_goal_bonus",
            source_id=str(when),
            reason="daily_goal",
            metadata={"target": target, "date": str(when)},
        )
        bonus_awarded = DAILY_GOAL_BONUS_XP if tx else 0
        progress.bonus_awarded = True
        progress.save(update_fields=["bonus_awarded"])
        # Also record the streak activity.
        from . import streak_v2
        streak_v2.record_learning_activity(
            user, "daily_goal_completed",
            xp_earned=bonus_awarded, on_date=when,
            metadata={"target": target},
        )

    return progress, just_completed, bonus_awarded


def is_daily_goal_completed(user, on_date: Optional[_date] = None) -> bool:
    when = on_date or timezone.localdate()
    return DailyGoalProgress.objects.filter(
        user=user, date=when, completed=True,
    ).exists()


def get_daily_goal_summary(user, on_date: Optional[_date] = None) -> dict:
    """Return a small dict the Summary template can render directly."""
    when = on_date or timezone.localdate()
    goal = get_or_create_daily_goal(user)
    progress = DailyGoalProgress.objects.filter(user=user, date=when).first()
    earned = progress.xp_earned if progress else 0
    target = goal.target_value or DEFAULT_TARGET_XP
    return {
        "goal_type": goal.goal_type,
        "target": target,
        "earned": earned,
        "remaining": max(0, target - earned),
        "pct": min(100, int(round(earned * 100 / max(1, target)))),
        "completed": bool(progress and progress.completed),
        "bonus_awarded": bool(progress and progress.bonus_awarded),
        "bonus_value": DAILY_GOAL_BONUS_XP,
    }
