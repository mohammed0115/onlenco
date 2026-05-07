"""AI usage logging + per-user daily limits.

Public API:
  log_usage(user, feature, *, model="", prompt_tokens=0, completion_tokens=0,
            estimated_cost=0, success=True, error_message="")
  is_within_limit(user, feature) -> bool
  daily_count(user, feature) -> int

Limits depend on the user's role/subscription. Free tiers get small daily
budgets; admins are unlimited.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Optional

from django.utils import timezone

from core.models import AIUsageLog


# Feature → (free_per_day, premium_per_day)
DAILY_LIMITS: dict[str, tuple[int, int]] = {
    "tutor": (20, 200),
    "error_analysis": (30, 500),
    "exercise_generation": (10, 100),
    "placement": (3, 10),
    "dictionary": (50, 1000),
    "other": (10, 100),
}


def log_usage(
    user,
    feature: str,
    *,
    model: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated_cost: float | Decimal = 0,
    success: bool = True,
    error_message: str = "",
) -> AIUsageLog:
    log = AIUsageLog.objects.create(
        user=user if (user is not None and getattr(user, "is_authenticated", True)) else None,
        feature=feature,
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost=Decimal(str(estimated_cost or 0)),
        success=success,
        error_message=(error_message or "")[:500],
    )
    if not success:
        try:
            from notifications import constants as C
            from notifications.services import NotificationService
            NotificationService().notify_admins(
                C.AI_FAILURE,
                payload={
                    "feature": feature,
                    "model": model or "",
                    "error_message": (error_message or "")[:300],
                    "at": log.created_at.isoformat(),
                    "cta_url": "/admin-analytics/learning/",
                    "cta_label": "Open analytics",
                    "dedup_key": f"ai_failure:{feature}:{(error_message or '')[:60]}",
                },
                priority=C.PRIORITY_HIGH,
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "ai_usage: admin alert failed", exc_info=True
            )
    return log


def daily_count(user, feature: str) -> int:
    if user is None or not getattr(user, "is_authenticated", True):
        return 0
    since = timezone.now() - timedelta(hours=24)
    return AIUsageLog.objects.filter(
        user=user, feature=feature, created_at__gte=since
    ).count()


def _user_tier(user) -> str:
    if not user or not getattr(user, "is_authenticated", True):
        return "free"
    profile = getattr(user, "profile", None)
    if profile is None:
        return "free"
    if profile.is_admin:
        return "admin"
    if profile.is_subscribed:
        return "premium"
    return "free"


HIGH_USAGE_NOTIFY_RATIO = 0.8


def is_within_limit(user, feature: str) -> bool:
    """True if the user can still call this feature today.

    When usage crosses `HIGH_USAGE_NOTIFY_RATIO` of the cap, also fans out
    an `ai_usage_high` admin alert (deduped per (user, feature, day)).
    """
    tier = _user_tier(user)
    if tier == "admin":
        return True
    free_cap, premium_cap = DAILY_LIMITS.get(feature, (10, 100))
    cap = premium_cap if tier == "premium" else free_cap
    used = daily_count(user, feature)
    if cap > 0 and used == int(cap * HIGH_USAGE_NOTIFY_RATIO):
        try:
            from notifications import constants as C
            from notifications.services import NotificationService
            from django.utils import timezone
            NotificationService().notify_admins(
                C.AI_USAGE_HIGH,
                payload={
                    "feature": feature,
                    "username": getattr(user, "username", "anonymous"),
                    "daily_count": used,
                    "limit": cap,
                    "cta_url": "/admin-analytics/learning/",
                    "cta_label": "Open analytics",
                    "dedup_key": f"ai_high:{feature}:{getattr(user, 'id', 'a')}:{timezone.now().date().isoformat()}",
                },
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning("ai_usage_high notify failed", exc_info=True)
    return used < cap
