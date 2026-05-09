"""Seed default ExamBlueprint rows from constants.DEFAULT_BLUEPRINTS."""
from django.core.management.base import BaseCommand

from exams.services.exam_blueprint_service import seed_default_blueprints


class Command(BaseCommand):
    help = "Create / update the canonical ExamBlueprint rows."

    def handle(self, *args, **opts):
        created, updated = seed_default_blueprints()
        self.stdout.write(self.style.SUCCESS(
            f"ExamBlueprint seed: created={created} updated={updated}"
        ))
