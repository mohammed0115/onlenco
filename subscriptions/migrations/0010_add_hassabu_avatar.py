"""Seed Hassabu — the 4th tutor avatar.

Hassabu is the platform owner; his photo is bundled at
``static/img/avatars/hassabu_male_teacher.jpg`` and his voice maps to
the same male provider voice as Omar (``ash`` via the
``onyx_professional`` VoiceProfile resolved by
``preference_service._voice_for_gender('male')``).

Voice cloning to Hassabu's real voice (consented) is a separate
project on a feature branch — see Phase 5 voice-cloning POC. This
migration only adds the avatar so the existing OpenAI Realtime stack
can serve him with the deepest available male voice today.
"""
from __future__ import annotations

from django.db import migrations


HASSABU = {
    "code": "hassabu_male_teacher",
    "name_en": "Hassabu — Founder & Mentor",
    "name_ar": "حسبو — المؤسس والمرشد",
    "gender": "male",
    "style": "professional",
    "sort_order": 15,           # sits between Omar (20) and Layla (10)
    "is_active": True,
}


def seed(apps, schema_editor):
    Avatar = apps.get_model("subscriptions", "AvatarProfile")
    Avatar.objects.update_or_create(code=HASSABU["code"], defaults=HASSABU)


def unseed(apps, schema_editor):
    Avatar = apps.get_model("subscriptions", "AvatarProfile")
    Avatar.objects.filter(code=HASSABU["code"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0009_remap_retired_realtime_voices"),
    ]
    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
