"""Send daily and/or weekly admin summaries + at-risk student alerts."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from notifications import constants as C
from notifications.services import NotificationService
from notifications.services.digest_service import DigestService


class Command(BaseCommand):
    help = "Send admin digest emails: --window=daily|weekly|all (default daily)."

    def add_arguments(self, parser):
        parser.add_argument("--window", choices=["daily", "weekly", "all"], default="daily")
        parser.add_argument("--include-at-risk", action="store_true", default=False)

    def handle(self, *args, window: str = "daily", include_at_risk: bool = False, **options):
        digests = DigestService()
        notifier = NotificationService()

        if window in ("daily", "all"):
            digests.send_daily_admin_summary()
            self.stdout.write(self.style.SUCCESS("Sent daily admin summary."))

        if window in ("weekly", "all"):
            digests.send_weekly_admin_summary()
            self.stdout.write(self.style.SUCCESS("Sent weekly admin summary."))

        if include_at_risk:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            for user_id in digests.find_at_risk_students():
                user = User.objects.filter(pk=user_id).first()
                if not user:
                    continue
                notifier.notify_admins(
                    C.AT_RISK_STUDENT,
                    payload={
                        "username": user.username,
                        "avg_mastery": "<40",
                        "last_active": "—",
                        "cta_url": "/admin-analytics/learning/",
                        "cta_label": "Open analytics",
                        "dedup_key": f"at_risk:{user_id}",
                    },
                    priority=C.PRIORITY_HIGH,
                )
            self.stdout.write(self.style.SUCCESS("At-risk alerts dispatched."))
