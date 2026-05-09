"""Purge raw audio blobs older than `SPEECH_AUDIO_RETENTION_DAYS`.

We keep the SpeakingAttempt row (transcript + duration + confidence
remain auditable) and only delete the FileField. Run nightly via cron
or whatever scheduler the deployment uses.

Idempotent: runs that find nothing to delete print "0 cleaned".
"""
from __future__ import annotations

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from speech.models import SpeakingAttempt


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Delete audio files on SpeakingAttempt rows older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Show what would be deleted without touching storage.",
        )
        parser.add_argument(
            "--days", type=int, default=None,
            help="Override settings.SPEECH_AUDIO_RETENTION_DAYS for this run.",
        )

    def handle(self, *args, **opts):
        days = opts.get("days") or getattr(settings, "SPEECH_AUDIO_RETENTION_DAYS", 7)
        cutoff = timezone.now() - timezone.timedelta(days=days)
        qs = SpeakingAttempt.objects.filter(
            created_at__lt=cutoff,
        ).exclude(audio_file="").exclude(audio_file__isnull=True)
        total = qs.count()
        if not total:
            self.stdout.write(self.style.SUCCESS(f"0 cleaned (cutoff: {cutoff.isoformat()})"))
            return

        if opts.get("dry_run"):
            self.stdout.write(f"Would delete {total} audio file(s) older than {days} days.")
            return

        deleted = 0
        for att in qs.iterator():
            try:
                if att.audio_file:
                    att.audio_file.delete(save=False)
                att.audio_file = None
                att.save(update_fields=["audio_file"])
                deleted += 1
            except Exception:
                logger.exception("Failed to delete audio for SpeakingAttempt id=%s", att.id)

        self.stdout.write(self.style.SUCCESS(
            f"Cleaned {deleted}/{total} audio files older than {days} days."
        ))
