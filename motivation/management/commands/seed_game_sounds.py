"""Seed the default gamification audio cues (GameEventSound).

Mirrors migration 0006_seed_game_event_sounds as a re-runnable command,
consistent with the other seed_* commands. Idempotent — update_or_create
on the stable `code`, and `audio_url` / `fallback_audio_path` are NOT in
the defaults, so re-running never wipes audio an admin set from the
Control Center. Safe to run on every deploy.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from motivation.models import GameEventSound


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


class Command(BaseCommand):
    help = "Seed the default gamification audio cues (GameEventSound)."

    def handle(self, *args, **options):
        created = updated = 0
        for sound in SOUNDS:
            _, was_created = GameEventSound.objects.update_or_create(
                code=sound["code"], defaults=sound,
            )
            created += int(was_created)
            updated += int(not was_created)
        total = GameEventSound.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Game sounds: {created} created, {updated} updated, {total} total."
        ))
