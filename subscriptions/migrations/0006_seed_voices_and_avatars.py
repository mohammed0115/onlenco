"""Seed the initial voice + avatar catalogue.

Voices map onto OpenAI Realtime voice IDs (alloy, echo, fable, onyx,
nova, shimmer). Admins can disable or rename any of them from the
Control Center; this migration just supplies a sensible starting set
so the tutor screen has something to pick from on day one.
"""
from django.db import migrations


VOICES = [
    {
        "code": "alloy_friendly",
        "name_en": "Alloy — Friendly Tutor",
        "name_ar": "آلوي — مدرّس ودود",
        "provider_voice_id": "alloy",
        "voice_type": "neutral",
        "style": "friendly_tutor",
        "accent": "neutral",
        "tone": "normal",
        "sort_order": 10,
    },
    {
        "code": "nova_calm",
        "name_en": "Nova — Calm Teacher",
        "name_ar": "نوفا — مدرّسة هادئة",
        # GA-era Realtime API: 'nova' was retired; 'shimmer' is the
        # closest warm-female voice that the new endpoint accepts.
        "provider_voice_id": "shimmer",
        "voice_type": "female",
        "style": "calm_teacher",
        "accent": "american",
        "tone": "calm",
        "sort_order": 20,
    },
    {
        "code": "shimmer_energetic",
        "name_en": "Shimmer — Energetic Coach",
        "name_ar": "شيمر — مدرّبة نشيطة",
        "provider_voice_id": "shimmer",
        "voice_type": "female",
        "style": "energetic_coach",
        "accent": "american",
        "tone": "energetic",
        "sort_order": 30,
    },
    {
        "code": "onyx_professional",
        "name_en": "Onyx — Professional Instructor",
        "name_ar": "أونيكس — معلّم محترف",
        # GA-era Realtime API: 'onyx' was retired; 'ash' is the
        # closest deep-male voice accepted by the new endpoint.
        "provider_voice_id": "ash",
        "voice_type": "male",
        "style": "professional",
        "accent": "british",
        "tone": "deep",
        "sort_order": 40,
    },
    {
        "code": "echo_neutral",
        "name_en": "Echo — Neutral Voice",
        "name_ar": "إيكو — صوت محايد",
        "provider_voice_id": "echo",
        "voice_type": "male",
        "style": "friendly_tutor",
        "accent": "neutral",
        "tone": "normal",
        "sort_order": 50,
    },
    {
        "code": "fable_soft",
        "name_en": "Fable — Soft Teacher",
        "name_ar": "فيبل — مدرّس لطيف",
        # GA-era Realtime API: 'fable' was retired; 'ballad' is the
        # closest soft-storyteller voice accepted by the new endpoint.
        "provider_voice_id": "ballad",
        "voice_type": "neutral",
        "style": "calm_teacher",
        "accent": "british",
        "tone": "soft",
        "sort_order": 60,
    },
]


AVATARS = [
    {
        "code": "layla_female_teacher",
        "name_en": "Layla — Friendly Teacher",
        "name_ar": "ليلى — مدرّسة ودودة",
        "gender": "female",
        "style": "casual",
        "sort_order": 10,
    },
    {
        "code": "omar_male_teacher",
        "name_en": "Omar — Professional Teacher",
        "name_ar": "عمر — معلّم محترف",
        "gender": "male",
        "style": "professional",
        "sort_order": 20,
    },
    {
        "code": "sara_energetic",
        "name_en": "Sara — Energetic Coach",
        "name_ar": "سارة — مدرّبة نشيطة",
        "gender": "female",
        "style": "energetic",
        "sort_order": 30,
    },
    {
        "code": "anonymous",
        "name_en": "Anonymous (no avatar)",
        "name_ar": "بدون صورة",
        "gender": "neutral",
        "style": "casual",
        "sort_order": 90,
    },
]


def seed(apps, schema_editor):
    Voice = apps.get_model("subscriptions", "VoiceProfile")
    Avatar = apps.get_model("subscriptions", "AvatarProfile")
    for v in VOICES:
        Voice.objects.update_or_create(code=v["code"], defaults=v)
    for a in AVATARS:
        Avatar.objects.update_or_create(code=a["code"], defaults=a)


def unseed(apps, schema_editor):
    Voice = apps.get_model("subscriptions", "VoiceProfile")
    Avatar = apps.get_model("subscriptions", "AvatarProfile")
    Voice.objects.filter(code__in=[v["code"] for v in VOICES]).delete()
    Avatar.objects.filter(code__in=[a["code"] for a in AVATARS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0005_avatarprofile_voiceprofile_and_more"),
    ]
    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
