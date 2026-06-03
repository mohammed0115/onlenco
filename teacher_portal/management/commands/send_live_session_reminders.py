"""Send the 30-minute reminder for upcoming live sessions.

Run from the scheduler every ~5 minutes:

    python manage.py send_live_session_reminders

Idempotent — each session reminds its students once (guarded by
``LiveSession.reminder_sent_at``).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from teacher_portal.services import live_session_service


class Command(BaseCommand):
    help = "Notify students of live sessions starting within the next 30 minutes."

    def handle(self, *args, **options):
        result = live_session_service.send_reminders()
        self.stdout.write(self.style.SUCCESS(
            f"Live-session reminders: {result['sessions']} session(s), "
            f"{result['students']} student notification(s)."
        ))
