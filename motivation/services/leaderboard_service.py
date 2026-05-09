"""Leaderboard service.

Public API:
    rebuild_period(period, today=None) -> int            (recompute one period)
    rebuild_all(today=None) -> dict                       (cron entry-point)
    top_n(period, n=10, today=None) -> list[LeaderboardEntry]
    user_entry(user, period, today=None) -> LeaderboardEntry | None

Privacy: only users whose `MotivationPreference.show_on_leaderboard` is
True are written. Opt-out users still earn XP normally; they just don't
appear on the public board and `user_entry()` returns None.
"""
from __future__ import annotations

import logging
from datetime import date as _date, timedelta
from typing import List, Optional

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from ..models import (
    LearnerActivitySnapshot,
    LeaderboardEntry,
    MotivationPreference,
)

logger = logging.getLogger(__name__)


def _period_window(period: str, today: _date) -> tuple[_date, _date]:
    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    elif period == "monthly":
        start = today.replace(day=1)
        next_month = (start + timedelta(days=32)).replace(day=1)
        end = next_month - timedelta(days=1)
    else:
        raise ValueError(f"Unknown period: {period}")
    return start, end


def _xp_for_user(user_id: int, start: _date, end: _date) -> int:
    """Sum of XP awarded across the window from per-day snapshot metadata."""
    total = 0
    rows = LearnerActivitySnapshot.objects.filter(
        user_id=user_id, date__gte=start, date__lte=end,
    ).values_list("metadata", flat=True)
    for meta in rows:
        try:
            total += int((meta or {}).get("xp_awarded", 0) or 0)
        except Exception:
            continue
    return total


def _opted_out_user_ids() -> set:
    """Users who explicitly opted OUT of the leaderboard."""
    return set(
        MotivationPreference.objects
        .filter(show_on_leaderboard=False)
        .values_list("user_id", flat=True)
    )


def rebuild_period(period: str, today: Optional[_date] = None) -> int:
    """Recompute the leaderboard for `period`. Returns rows written."""
    if today is None:
        today = timezone.localdate()
    start, end = _period_window(period, today)

    opted_out = _opted_out_user_ids()
    user_ids = set(
        LearnerActivitySnapshot.objects
        .filter(date__gte=start, date__lte=end)
        .values_list("user_id", flat=True)
        .distinct()
    )
    user_ids -= opted_out
    if not user_ids:
        # Wipe the period so a previously-published board doesn't go stale.
        LeaderboardEntry.objects.filter(
            period=period, period_start=start
        ).delete()
        return 0

    # Compute XP per opted-in user.
    rows = []
    for uid in user_ids:
        xp = _xp_for_user(uid, start, end)
        if xp <= 0:
            continue
        rows.append({"user_id": uid, "xp": xp})

    rows.sort(key=lambda r: r["xp"], reverse=True)

    with transaction.atomic():
        LeaderboardEntry.objects.filter(
            period=period, period_start=start
        ).delete()
        new_rows = []
        for rank, r in enumerate(rows, start=1):
            new_rows.append(LeaderboardEntry(
                user_id=r["user_id"],
                period=period,
                period_start=start,
                period_end=end,
                xp=r["xp"],
                rank=rank,
                display_name=_display_name_for(r["user_id"]),
            ))
        if new_rows:
            LeaderboardEntry.objects.bulk_create(new_rows)
    return len(rows)


def _display_name_for(user_id: int) -> str:
    """Best-effort public display name. Falls back to 'Learner #N' so we
    don't leak emails."""
    try:
        from django.contrib.auth import get_user_model
        u = get_user_model().objects.filter(pk=user_id).first()
        if not u:
            return f"Learner #{user_id}"
        prof = getattr(u, "profile", None)
        name = (getattr(prof, "full_name", "") or "").strip()
        if name:
            return name[:60]
    except Exception:
        pass
    return f"Learner #{user_id}"


def rebuild_all(today: Optional[_date] = None) -> dict:
    """Cron-style: rebuild weekly + monthly. Returns count summary."""
    if today is None:
        today = timezone.localdate()
    weekly = rebuild_period("weekly", today)
    monthly = rebuild_period("monthly", today)
    return {"weekly": weekly, "monthly": monthly}


def top_n(period: str, n: int = 10, today: Optional[_date] = None) -> List[LeaderboardEntry]:
    if today is None:
        today = timezone.localdate()
    start, _ = _period_window(period, today)
    return list(
        LeaderboardEntry.objects
        .filter(period=period, period_start=start)
        .order_by("rank")[:n]
    )


def user_entry(user, period: str, today: Optional[_date] = None) -> Optional[LeaderboardEntry]:
    if today is None:
        today = timezone.localdate()
    start, _ = _period_window(period, today)
    return (
        LeaderboardEntry.objects
        .filter(user=user, period=period, period_start=start)
        .first()
    )
