"""Decide what kind of plan today should be.

The "plan type" gates downstream behavior: a comeback plan is shorter
(4 items instead of 5–8) and skips review-mistake content; an exam-prep
plan biases the content selector toward `quiz` items at higher
difficulty; a streak-recovery plan keeps the tone gentle.
"""
from __future__ import annotations

import logging
from datetime import date as _date

logger = logging.getLogger(__name__)

# Inactivity threshold for "comeback" mode (days since last activity).
INACTIVE_DAYS_FOR_COMEBACK = 3


def decide_plan_type(user, on_date: _date, profile, learning_profile) -> str:
    """Return one of the PLAN_TYPE_CHOICES values.

    Decision order:
      1. profile.cefr_level == "A0" and profile.onboarding_path == "beginner_start"
         → "beginner_start"
      2. user has been inactive for >= INACTIVE_DAYS_FOR_COMEBACK
         → "streak_recovery"
      3. user has any active weakness with priority >= 7.0
         → "weakness_review"
      4. profile.onboarding_path == "placement_test" and profile.cefr_level
         → "placement_based"
      5. else → "normal_daily_plan"
    """
    # 1. A0 beginner path
    if (profile and getattr(profile, "cefr_level", None) == "A0"
            and getattr(profile, "onboarding_path", "") == "beginner_start"):
        return "beginner_start"

    # 2. Inactive student
    try:
        from motivation.services import streak_service
        inactive_days = streak_service.get_inactive_days(user, on_date)
        if inactive_days >= INACTIVE_DAYS_FOR_COMEBACK:
            return "streak_recovery"
    except Exception:
        logger.exception("streak_service unavailable")

    # 3. Weakness-driven plan
    try:
        from learning_core.models import UserWeakness
        has_high_priority = UserWeakness.objects.filter(
            user=user, status="active", priority_score__gte=7.0
        ).exists()
        if has_high_priority:
            return "weakness_review"
    except Exception:
        pass

    # 4. Placement-based
    if profile and getattr(profile, "onboarding_path", "") == "placement_test":
        if getattr(profile, "cefr_level", None):
            return "placement_based"

    return "normal_daily_plan"


def item_count_for_plan_type(plan_type: str, *, min_items: int, max_items: int,
                              comeback_items: int) -> tuple[int, int]:
    """Return (target_min, target_max) item counts for this plan type."""
    if plan_type == "streak_recovery":
        return (max(3, comeback_items - 1), comeback_items)
    if plan_type == "beginner_start":
        return (5, 6)  # always a fixed 6-item A0 topic
    return (min_items, max_items)
