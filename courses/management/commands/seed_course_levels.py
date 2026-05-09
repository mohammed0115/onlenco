"""Seed the canonical CEFR levels (A0 → C2) into `CourseLevel`.

Idempotent — re-running updates display order/names but preserves IDs."""
from django.core.management.base import BaseCommand

from courses.models import CourseLevel

LEVELS = [
    ("A0", "Beginner — Pre-A1",   "Absolute beginner; no prior English."),
    ("A1", "Elementary",           "Basic phrases and everyday expressions."),
    ("A2", "Pre-Intermediate",     "Routine tasks and direct exchanges."),
    ("B1", "Intermediate",         "Familiar topics, simple opinions."),
    ("B2", "Upper-Intermediate",   "Complex texts, abstract topics."),
    ("C1", "Advanced",             "Fluent, spontaneous, professional use."),
    ("C2", "Mastery",              "Near-native command."),
]


class Command(BaseCommand):
    help = "Seed CEFR CourseLevel rows (A0..C2)."

    def handle(self, *args, **opts):
        created = updated = 0
        for order, (code, name, desc) in enumerate(LEVELS):
            obj, was_created = CourseLevel.objects.update_or_create(
                code=code,
                defaults={
                    "name": name, "description": desc,
                    "order": order, "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"CourseLevel: created={created} updated={updated} total={CourseLevel.objects.count()}"
        ))
