"""Evaluate spend / failure thresholds and dispatch alerts.

Run hourly.

    python manage.py ai_usage_alerts
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from ...services import alert_service


class Command(BaseCommand):
    help = "Evaluate AI usage budget/failure thresholds and send alerts."

    def handle(self, *args, **opts):
        alerts = alert_service.evaluate_alerts()
        if not alerts:
            self.stdout.write(self.style.SUCCESS("No AI usage alerts."))
            return
        for a in alerts:
            self.stdout.write(self.style.WARNING(f"[{a['type']}] {a['message']}"))
        self.stdout.write(self.style.SUCCESS(f"{len(alerts)} alert(s) dispatched."))
