"""Optional Celery tasks mirroring the management commands.

Celery is an OPTIONAL stub in this project (see onlenco/celery.py). These
tasks are only registered when Celery is installed and configured; the
management commands are the supported scheduler otherwise. Wire into Celery
beat like:

    CELERY_BEAT_SCHEDULE = {
        "aggregate-ai-usage": {"task": "ai_usage.aggregate_ai_usage_daily",
                               "schedule": crontab(hour=0, minute=30)},
        "update-student-limits": {"task": "ai_usage.update_student_daily_limits",
                                  "schedule": crontab(hour=0, minute=5)},
        "ai-usage-alerts": {"task": "ai_usage.ai_usage_alerts",
                            "schedule": crontab(minute=0)},
    }
"""
from __future__ import annotations

try:
    from celery import shared_task
except Exception:  # pragma: no cover - Celery not installed
    shared_task = None


if shared_task is not None:  # pragma: no cover - exercised only with Celery
    from datetime import timedelta

    from django.contrib.auth import get_user_model
    from django.utils import timezone

    from .services import aggregation, alert_service, limit_service

    @shared_task(name="ai_usage.aggregate_ai_usage_daily")
    def aggregate_ai_usage_daily(date_str: str | None = None):
        day = timezone.localdate() - timedelta(days=1)
        if date_str:
            from datetime import datetime
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
        return aggregation.aggregate_day(day)

    @shared_task(name="ai_usage.update_student_daily_limits")
    def update_student_daily_limits():
        User = get_user_model()
        count = 0
        for user in User.objects.filter(is_active=True).iterator():
            limit_service.create_or_update_daily_limit(user)
            count += 1
        return count

    @shared_task(name="ai_usage.ai_usage_alerts")
    def ai_usage_alerts():
        return alert_service.evaluate_alerts()
