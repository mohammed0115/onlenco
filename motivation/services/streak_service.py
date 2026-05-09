"""Streak utilities — reads from LearnerActivitySnapshot."""
from __future__ import annotations

from datetime import date as _date, timedelta
from typing import Optional

from django.utils import timezone

from .. import constants as C
from ..models import LearnerActivitySnapshot


def get_current_streak(user, on_date: Optional[_date] = None) -> int:
    """Number of consecutive days ending at `on_date` with activity."""
    if on_date is None:
        on_date = timezone.localdate()
    snap = LearnerActivitySnapshot.objects.filter(user=user, date=on_date).first()
    if snap:
        return snap.current_streak_days or 0
    # Fall back to recent history
    last = (
        LearnerActivitySnapshot.objects
        .filter(user=user, date__lt=on_date)
        .order_by("-date")
        .first()
    )
    if not last:
        return 0
    if (on_date - last.date).days <= 1:
        return last.current_streak_days or 0
    return 0


def get_inactive_days(user, on_date: Optional[_date] = None) -> int:
    if on_date is None:
        on_date = timezone.localdate()
    snap = LearnerActivitySnapshot.objects.filter(user=user, date=on_date).first()
    if snap:
        return snap.inactive_days or 0
    last = (
        LearnerActivitySnapshot.objects
        .filter(user=user, date__lt=on_date)
        .order_by("-date")
        .first()
    )
    if not last:
        return 0
    return max(0, (on_date - last.date).days)


def is_streak_milestone(streak_days: int) -> bool:
    return streak_days in C.STREAK_MILESTONES


def upcoming_milestone(streak_days: int) -> Optional[int]:
    for m in C.STREAK_MILESTONES:
        if m > streak_days:
            return m
    return None
