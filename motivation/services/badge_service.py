"""Badge awarding — small, decorative, separate from achievements."""
from __future__ import annotations

from typing import Optional, Tuple

from django.db import transaction

from ..models import UserBadge


def award_badge(
    user,
    *,
    badge_code: str,
    badge_name: str,
    description: str = "",
    metadata: Optional[dict] = None,
) -> Tuple[UserBadge, bool]:
    """Idempotent: returns (badge, created)."""
    with transaction.atomic():
        badge, created = UserBadge.objects.get_or_create(
            user=user,
            badge_code=badge_code,
            defaults={
                "badge_name": badge_name,
                "description": description,
                "metadata": metadata or {},
            },
        )
    return badge, created


def streak_badge_for(days: int) -> Optional[dict]:
    """Return a badge spec for a given streak length, or None."""
    table = {
        3:   {"code": "streak_3",   "name": "3-day streak",   "name_ar": "سلسلة 3 أيام"},
        7:   {"code": "streak_7",   "name": "7-day streak",   "name_ar": "سلسلة 7 أيام"},
        14:  {"code": "streak_14",  "name": "14-day streak",  "name_ar": "سلسلة 14 يوماً"},
        30:  {"code": "streak_30",  "name": "30-day streak",  "name_ar": "سلسلة 30 يوماً"},
        60:  {"code": "streak_60",  "name": "60-day streak",  "name_ar": "سلسلة 60 يوماً"},
        100: {"code": "streak_100", "name": "100-day streak", "name_ar": "سلسلة 100 يوم"},
    }
    return table.get(days)
