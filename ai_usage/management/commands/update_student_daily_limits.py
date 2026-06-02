"""Create / refresh today's StudentDailyAILimit rows from subscriptions.

Run nightly at 00:00. Idempotent — re-running just refreshes the projection.

    python manage.py update_student_daily_limits
    python manage.py update_student_daily_limits --user=<id>
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from ...services import limit_service


class Command(BaseCommand):
    help = "Create/refresh StudentDailyAILimit rows for active students."

    def add_arguments(self, parser):
        parser.add_argument("--user", type=int, default=None)

    def handle(self, *args, **opts):
        User = get_user_model()
        qs = User.objects.filter(is_active=True)
        if opts["user"]:
            qs = qs.filter(id=opts["user"])

        count = 0
        for user in qs.iterator():
            try:
                limit_service.create_or_update_daily_limit(user)
                count += 1
            except Exception as exc:  # pragma: no cover - keep going on per-user errors
                self.stderr.write(f"user {user.id}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Refreshed {count} student daily limits."))
