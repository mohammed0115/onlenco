"""Seed the catalog from `motivation.constants.DEFAULT_ACHIEVEMENTS`.

Fresh installs need these rows for `achievement_service` to award
anything (`first_lesson_completed`, etc.). Without this migration the
catalog is empty until an operator remembers to run
`manage.py seed_achievements`.

Idempotent on rerun: we use `update_or_create(code=...)` so re-applying
the migration tracks any subsequent edits to the constants without
duplicating rows.
"""
from django.db import migrations


def seed_achievements(apps, schema_editor):
    Achievement = apps.get_model("motivation", "Achievement")
    from motivation import constants as C
    for row in C.DEFAULT_ACHIEVEMENTS:
        (code, category, threshold, xp,
         name_en, desc_en, name_ar, desc_ar, icon) = row
        Achievement.objects.update_or_create(
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


def noop_reverse(apps, schema_editor):
    # Reversing the migration leaves the rows in place; achievements
    # are catalog data, not user-owned state. Removing them would
    # cascade-delete UserAchievement rows in some configurations.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("motivation", "0003_alter_achievement_options_alter_challenge_options_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_achievements, noop_reverse),
    ]
