"""Purge AI Tutor conversations older than the retention window.

Run from cron / the scheduler service so the conversation log doesn't
grow without bound and so we honour the privacy contract documented on
the profile page ("AI Tutor conversations are kept for {N} days").

Defaults to 90 days. Override with ``--days N`` or by setting
``TUTOR_CONVERSATION_RETENTION_DAYS`` in settings.
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from tutor.models import TutorConversation


DEFAULT_RETENTION_DAYS = 90


class Command(BaseCommand):
    help = "Delete AI Tutor conversations whose updated_at is older than N days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Retention window in days (overrides settings.TUTOR_CONVERSATION_RETENTION_DAYS).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report how many conversations would be deleted without touching the DB.",
        )

    def handle(self, *args, **opts):
        days = opts.get("days")
        if days is None:
            days = int(getattr(settings, "TUTOR_CONVERSATION_RETENTION_DAYS", DEFAULT_RETENTION_DAYS))
        if days <= 0:
            self.stdout.write(self.style.WARNING(
                "Retention <= 0 disables purging; nothing to do."
            ))
            return

        cutoff = timezone.now() - timedelta(days=days)
        qs = TutorConversation.objects.filter(updated_at__lt=cutoff)
        count = qs.count()

        if opts.get("dry_run"):
            self.stdout.write(self.style.SUCCESS(
                f"[dry-run] would delete {count} conversation(s) older than {days} day(s)."
            ))
            return

        deleted, _detail = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Deleted {deleted} record(s) from conversations older than {days} day(s)."
        ))
