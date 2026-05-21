"""Send each teacher a daily digest of pending work.

A digest is an in-app ``TEACHER_DAILY_DIGEST`` notification summarising
submissions awaiting review and content sent back for revision.
Teachers with nothing pending are skipped. Idempotent enough to run
once a day from the scheduler.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from teacher_portal.services import notification_service


class Command(BaseCommand):
    help = "Send each teacher a daily digest of pending work."

    def handle(self, *args, **opts):
        result = notification_service.send_daily_digests()
        self.stdout.write(self.style.SUCCESS(
            f"Teacher digests: {result['digests_sent']} sent "
            f"({result['teachers']} teachers checked)."
        ))
