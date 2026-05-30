"""Streak source-of-truth — Phase 5.

The older `streak_service.get_current_streak` reads from
LearnerActivitySnapshot. Phase 5 introduces an explicit
`StudentStreak` row plus a `StreakActivity` log so:

  * Multiple challenge_completed events on the same day = ONE streak day.
  * The dashboard can render "current 7, longest 12" without scanning
    every snapshot.
  * Tests can deterministically advance the clock.
"""
from __future__ import annotations

from datetime import date as _date, timedelta
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import StreakActivity, StudentStreak


# Activity types that DO count for the daily streak. Things like
# "challenge_started" are recorded but DON'T move the needle.
COUNTING_TYPES = {
    "challenge_completed", "lesson_completed", "daily_goal_completed",
}


@transaction.atomic
def record_learning_activity(
    user,
    activity_type: str,
    *,
    xp_earned: int = 0,
    on_date: Optional[_date] = None,
    metadata: Optional[dict] = None,
) -> tuple[StudentStreak, bool]:
    """Log the activity and (maybe) advance the user's streak.

    Returns (streak, advanced) — `advanced=True` exactly when this call
    moved the streak forward by a day. A repeat of the same type on the
    same day returns `advanced=False`.
    """
    when = on_date or timezone.localdate()
    try:
        StreakActivity.objects.create(
            user=user, activity_date=when,
            activity_type=activity_type,
            xp_earned=int(xp_earned or 0),
            metadata=metadata or {},
        )
    except IntegrityError:
        # Same (user, date, type) already logged — idempotent.
        pass

    streak, _ = StudentStreak.objects.select_for_update().get_or_create(user=user)

    if activity_type not in COUNTING_TYPES:
        return streak, False

    last = streak.last_activity_date
    advanced = False

    if last is None:
        streak.current_streak = 1
        streak.last_activity_date = when
        advanced = True
    elif when == last:
        # Same-day repeat — no advance.
        pass
    elif when == last + timedelta(days=1):
        streak.current_streak = (streak.current_streak or 0) + 1
        streak.last_activity_date = when
        advanced = True
    elif when > last + timedelta(days=1):
        # Gap — reset.
        streak.current_streak = 1
        streak.last_activity_date = when
        advanced = True
    # else (when < last) — backdated event, ignore.

    if streak.current_streak > streak.longest_streak:
        streak.longest_streak = streak.current_streak

    streak.save()
    return streak, advanced


def get_streak(user) -> StudentStreak:
    streak, _ = StudentStreak.objects.get_or_create(user=user)
    return streak


def would_continue_streak(user, *, on_date: Optional[_date] = None) -> bool:
    """True if a counting activity TODAY would extend (not reset) the streak."""
    today = on_date or timezone.localdate()
    streak = get_streak(user)
    last = streak.last_activity_date
    if last is None or last == today:
        return True   # First-ever or same-day = always "continues"
    return last == today - timedelta(days=1)
