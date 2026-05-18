"""Seed the 5 default gamification audio cues.

Audio URLs are intentionally blank — admins set them from the Control
Center once they upload the project's sound assets. The frontend
gracefully degrades to silent-toast when the URL is empty, so this
migration is safe to ship as-is.
"""
from django.db import migrations


SOUNDS = [
    {
        "code": "success",
        "message_en": "Excellent work! Lesson complete.",
        "message_ar": "ممتاز! أنهيت الدرس.",
        "animation": "sparkle",
        "xp_callout_template_en": "+{xp} XP",
        "xp_callout_template_ar": "+{xp} نقطة",
    },
    {
        "code": "level_up",
        "message_en": "Level up! You reached level {level}.",
        "message_ar": "ترقية! وصلت إلى المستوى {level}.",
        "animation": "rocket",
        "xp_callout_template_en": "Level {level}",
        "xp_callout_template_ar": "المستوى {level}",
    },
    {
        "code": "bonus",
        "message_en": "Bonus XP earned!",
        "message_ar": "حصلت على نقاط مكافأة!",
        "animation": "sparkle",
        "xp_callout_template_en": "+{xp} XP",
        "xp_callout_template_ar": "+{xp} نقطة",
    },
    {
        "code": "streak",
        "message_en": "Streak maintained — {days} days in a row.",
        "message_ar": "أنت تحافظ على سلسلتك — {days} أيام متتالية.",
        "animation": "flame",
        "xp_callout_template_en": "{days} day streak",
        "xp_callout_template_ar": "سلسلة {days} أيام",
    },
    {
        "code": "achievement_unlocked",
        "message_en": "Achievement unlocked: {name}",
        "message_ar": "تم فتح إنجاز: {name}",
        "animation": "trophy",
        "xp_callout_template_en": "+{xp} XP",
        "xp_callout_template_ar": "+{xp} نقطة",
    },
]


def seed(apps, schema_editor):
    Sound = apps.get_model("motivation", "GameEventSound")
    for s in SOUNDS:
        Sound.objects.update_or_create(code=s["code"], defaults=s)


def unseed(apps, schema_editor):
    Sound = apps.get_model("motivation", "GameEventSound")
    Sound.objects.filter(code__in=[s["code"] for s in SOUNDS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("motivation", "0005_gameeventsound"),
    ]
    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
