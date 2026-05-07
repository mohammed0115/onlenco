"""DigestService — daily/weekly admin & student summaries."""
from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .. import constants as C
from .notification_service import NotificationService


class DigestService:
    def __init__(self, notification_service: NotificationService | None = None):
        self.notifier = notification_service or NotificationService()

    def send_daily_admin_summary(self) -> None:
        payload = self._daily_admin_payload()
        self.notifier.notify_admins(C.DAILY_ADMIN_SUMMARY, payload=payload)

    def send_weekly_admin_summary(self) -> None:
        payload = self._weekly_admin_payload()
        self.notifier.notify_admins(C.WEEKLY_ADMIN_SUMMARY, payload=payload)

    def _daily_admin_payload(self) -> dict:
        try:
            from analytics.services_learning import compute_learning_metrics
            metrics = compute_learning_metrics(days=1)
        except Exception:
            metrics = {}
        return {
            "window": "24h",
            "generated_at": timezone.now().isoformat(),
            "metrics": metrics,
        }

    def _weekly_admin_payload(self) -> dict:
        try:
            from analytics.services_learning import compute_learning_metrics
            metrics = compute_learning_metrics(days=7)
        except Exception:
            metrics = {}
        return {
            "window": "7d",
            "generated_at": timezone.now().isoformat(),
            "metrics": metrics,
        }

    def find_at_risk_students(self) -> list:
        """Return user IDs flagged at-risk by analytics. Used by admin alerts."""
        try:
            from learning_core.models import SkillMastery
            from django.db.models import Avg, Count
            qs = (
                SkillMastery.objects.values("user_id")
                .annotate(avg=Avg("mastery_score"), n=Count("id"))
                .filter(avg__lt=40.0, n__gte=1)
            )
            return [row["user_id"] for row in qs]
        except Exception:
            return []
