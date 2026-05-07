"""Email students who haven't attempted any exercise in the last N days."""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from notifications import constants as C
from notifications.services import NotificationService

User = get_user_model()


class Command(BaseCommand):
    help = "Email students inactive for more than --days days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=14)

    def handle(self, *args, days: int = 14, **options):
        from learning_core.models import ExerciseAttempt

        cutoff = timezone.now() - timedelta(days=days)
        recent_user_ids = ExerciseAttempt.objects.filter(
            created_at__gte=cutoff
        ).values_list("user_id", flat=True).distinct()
        candidates = User.objects.filter(date_joined__lte=cutoff).exclude(
            id__in=list(recent_user_ids)
        ).exclude(email="")
        notifier = NotificationService()
        sent = 0
        for user in candidates:
            notifier.trigger(
                C.INACTIVE_STUDENT_REMINDER,
                user=user,
                payload={
                    "cta_url": "/dashboard/",
                    "cta_label": "Come back",
                    "dedup_key": f"inactive:{user.id}:{timezone.now().date().isoformat()}",
                },
            )
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"Triggered inactive_student_reminder for {sent} user(s)."))
