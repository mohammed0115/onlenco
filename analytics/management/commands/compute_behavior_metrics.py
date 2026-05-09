"""Compute engagement / churn / learning-speed for every user."""
from django.core.management.base import BaseCommand

from analytics.services.scoring import persist_for_all


class Command(BaseCommand):
    help = "Recompute behavioral metrics for every learning profile."

    def handle(self, *args, **opts):
        result = persist_for_all()
        self.stdout.write(self.style.SUCCESS(
            f"Behavior metrics: users={result.get('users', 0)} errors={result.get('errors', 0)}"
        ))
