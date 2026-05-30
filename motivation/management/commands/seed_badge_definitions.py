"""Seed the BadgeDefinition catalog with the Phase 5 launch set.

Idempotent — re-running upserts each row by `code` and reports counts.
Run from your dev shell or in production after migrating:

    python manage.py seed_badge_definitions
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from motivation.services import badge_catalog


class Command(BaseCommand):
    help = "Seed/refresh the BadgeDefinition catalog used by the Challenge."

    def handle(self, *args, **options):
        created, updated = badge_catalog.seed_default_badges()
        self.stdout.write(self.style.SUCCESS(
            f"[OK] Badge catalog seeded: {created} created, {updated} updated, "
            f"{len(badge_catalog.DEFAULT_BADGES)} total."
        ))
