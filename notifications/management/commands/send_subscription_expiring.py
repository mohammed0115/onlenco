"""Email students whose subscription expires within N days.

Run from cron (or your scheduler):
    python manage.py send_subscription_expiring --days 3
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from notifications import constants as C
from notifications.services import NotificationService

User = get_user_model()


class Command(BaseCommand):
    help = "Email students whose subscription expires within --days days."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=3)

    def handle(self, *args, days: int = 3, **options):
        cutoff = timezone.now() + timedelta(days=days)
        notifier = NotificationService()
        sent = 0
        users = User.objects.filter(
            profile__subscription_status="active",
            profile__subscription_expires_at__isnull=False,
            profile__subscription_expires_at__lte=cutoff,
            profile__subscription_expires_at__gt=timezone.now(),
        ).exclude(email="")
        for user in users:
            notifier.trigger(
                C.SUBSCRIPTION_EXPIRING,
                user=user,
                payload={
                    "expires_at": user.profile.subscription_expires_at.strftime("%Y-%m-%d"),
                    "cta_url": "/payments/subscribe/",
                    "cta_label": "Renew now",
                    "dedup_key": f"expiring:{user.id}:{user.profile.subscription_expires_at.date().isoformat()}",
                },
            )
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"Triggered subscription_expiring for {sent} user(s)."))
