"""Spend / failure alerting.

Computes the current spend picture and, when a threshold is crossed, emails
``settings.AI_USAGE_ALERT_EMAILS`` (falling back to a log line + a TODO when
no email recipients are configured).
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Count, Sum
from django.utils import timezone

from .. import constants as C
from ..models import AIUsageLog
from .cost_calculator import safe_decimal

logger = logging.getLogger(__name__)


def _sum_cost(qs) -> Decimal:
    return safe_decimal(qs.aggregate(c=Sum("estimated_cost_usd"))["c"] or 0)


def current_spend() -> dict:
    today = timezone.localdate()
    month_start = today.replace(day=1)
    logs = AIUsageLog.objects
    today_cost = _sum_cost(logs.filter(usage_date=today))
    month_cost = _sum_cost(logs.filter(usage_date__gte=month_start))
    return {
        "date": today,
        "today_cost": today_cost,
        "month_cost": month_cost,
        "daily_budget": safe_decimal(getattr(settings, "AI_USAGE_DAILY_BUDGET_USD", "0")),
        "monthly_budget": safe_decimal(getattr(settings, "AI_USAGE_MONTHLY_BUDGET_USD", "0")),
    }


def evaluate_alerts() -> list[dict]:
    """Return the list of triggered alerts (also dispatched)."""
    alerts: list[dict] = []
    spend = current_spend()
    today = spend["date"]

    daily_budget = spend["daily_budget"]
    if daily_budget > 0 and spend["today_cost"] >= daily_budget:
        alerts.append({
            "type": "daily_budget_exceeded",
            "message": f"Daily AI spend ${spend['today_cost']} ≥ budget ${daily_budget}.",
        })

    monthly_budget = spend["monthly_budget"]
    if monthly_budget > 0 and spend["month_cost"] >= monthly_budget:
        alerts.append({
            "type": "monthly_budget_exceeded",
            "message": f"Monthly AI spend ${spend['month_cost']} ≥ budget ${monthly_budget}.",
        })

    # Abnormal per-user daily spend.
    user_threshold = safe_decimal(getattr(settings, "AI_USAGE_USER_DAILY_ALERT_USD", "0"))
    if user_threshold > 0:
        heavy = (
            AIUsageLog.objects.filter(usage_date=today, user__isnull=False)
            .values("user_id")
            .annotate(cost=Sum("estimated_cost_usd"))
            .filter(cost__gte=user_threshold)
            .order_by("-cost")
        )
        for row in heavy:
            alerts.append({
                "type": "user_abnormal_spend",
                "message": f"User {row['user_id']} spent ${row['cost']} today (≥ ${user_threshold}).",
            })

    # Failed-request spike (last hour).
    fail_threshold = int(getattr(settings, "AI_USAGE_FAILED_REQUESTS_ALERT", 0) or 0)
    if fail_threshold > 0:
        since = timezone.now() - timedelta(hours=1)
        fails = AIUsageLog.objects.filter(status=C.STATUS_FAILED, created_at__gte=since).count()
        if fails >= fail_threshold:
            alerts.append({
                "type": "failed_requests_spike",
                "message": f"{fails} failed AI requests in the last hour (≥ {fail_threshold}).",
            })

    if alerts:
        _dispatch(alerts)
    return alerts


def _dispatch(alerts: list[dict]) -> None:
    recipients = list(getattr(settings, "AI_USAGE_ALERT_EMAILS", []) or [])
    body = "\n".join(f"- [{a['type']}] {a['message']}" for a in alerts)
    subject = f"[Onlenco AI] {len(alerts)} usage alert(s)"
    if not recipients:
        # TODO: wire to the notifications app channel when email is unavailable.
        logger.warning("ai_usage alerts (no AI_USAGE_ALERT_EMAILS configured):\n%s", body)
        return
    try:
        send_mail(subject, body, None, recipients, fail_silently=True)
    except Exception:  # pragma: no cover - never raise from an alert
        logger.exception("ai_usage: alert email failed")
