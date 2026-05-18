"""Seed the 4 initial subscription plans.

Pricing follows the launch reference: 10 daily AI-Tutor minutes ≈
50,000 SDG / month. Plans use a linear scale; admins can override any
of these values from the Control Center without a code change.
"""
from django.db import migrations


INITIAL_PLANS = [
    {
        "code": "free_trial",
        "name_en": "Free Trial",
        "name_ar": "تجربة مجانية",
        "description_en": "5 free AI Tutor minutes — granted once at signup.",
        "description_ar": "5 دقائق مجانية للتحدث مع AI Tutor — تُمنح مرة واحدة عند التسجيل.",
        "price_sdg": 0,
        "ai_tutor_daily_minutes": 5,
        "library_audio_daily_minutes": 5,
        "is_free_trial": True,
        "sort_order": 0,
    },
    {
        "code": "starter_5m",
        "name_en": "Starter",
        "name_ar": "المبتدئ",
        "description_en": "5 AI Tutor minutes every day.",
        "description_ar": "5 دقائق يومياً للتحدث مع AI Tutor.",
        "price_sdg": 25000,
        "ai_tutor_daily_minutes": 5,
        "library_audio_daily_minutes": 15,
        "sort_order": 10,
    },
    {
        "code": "basic_10m",
        "name_en": "Basic",
        "name_ar": "أساسي",
        "description_en": "10 AI Tutor minutes every day.",
        "description_ar": "10 دقائق يومياً للتحدث مع AI Tutor.",
        "price_sdg": 50000,
        "ai_tutor_daily_minutes": 10,
        "library_audio_daily_minutes": 30,
        "sort_order": 20,
    },
    {
        "code": "plus_15m",
        "name_en": "Plus",
        "name_ar": "بلس",
        "description_en": "15 AI Tutor minutes every day.",
        "description_ar": "15 دقيقة يومياً للتحدث مع AI Tutor.",
        "price_sdg": 75000,
        "ai_tutor_daily_minutes": 15,
        "library_audio_daily_minutes": 45,
        "sort_order": 30,
    },
    {
        "code": "pro_30m",
        "name_en": "Pro",
        "name_ar": "احترافي",
        "description_en": "30 AI Tutor minutes every day.",
        "description_ar": "30 دقيقة يومياً للتحدث مع AI Tutor.",
        "price_sdg": 150000,
        "ai_tutor_daily_minutes": 30,
        "library_audio_daily_minutes": 60,
        "sort_order": 40,
    },
]


def seed_plans(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "SubscriptionPlan")
    for data in INITIAL_PLANS:
        Plan.objects.update_or_create(code=data["code"], defaults=data)


def unseed_plans(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "SubscriptionPlan")
    Plan.objects.filter(code__in=[p["code"] for p in INITIAL_PLANS]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(seed_plans, reverse_code=unseed_plans),
    ]
