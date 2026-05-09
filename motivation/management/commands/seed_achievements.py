"""Seed (or update) the catalog of achievements from constants."""
from django.core.management.base import BaseCommand

from motivation import constants as C
from motivation.models import Achievement


class Command(BaseCommand):
    help = "Seed/update Achievement rows from motivation.constants.DEFAULT_ACHIEVEMENTS."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for row in C.DEFAULT_ACHIEVEMENTS:
            (code, category, threshold, xp,
             name_en, desc_en, name_ar, desc_ar, icon) = row
            obj, was_created = Achievement.objects.update_or_create(
                code=code,
                defaults={
                    "name": name_en,
                    "description": desc_en,
                    "name_ar": name_ar,
                    "description_ar": desc_ar,
                    "category": category,
                    "threshold_value": threshold,
                    "xp_reward": xp,
                    "badge_icon": icon,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"Seeded achievements: {created} created, {updated} updated."
        ))
