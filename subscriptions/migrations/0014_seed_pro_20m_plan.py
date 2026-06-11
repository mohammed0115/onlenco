"""Seed the 20-minute AI-Tutor tier (product upgrade grid: 20 min = 100,000 SDG).

The launch reference grid is:
    10 min → 50,000 SDG   (basic_10m, already seeded)
    20 min → 100,000 SDG  (this migration)
    30 min → 150,000 SDG  (pro_30m, already seeded)

Additive + idempotent (``update_or_create``) so re-running is safe. Admins
can edit price/minutes/caps from the Control Center without code changes.
"""
from django.db import migrations


PRO_20M = {
    "code": "pro_20m",
    "name_en": "Pro 20",
    "name_ar": "برو ٢٠",
    "description_en": "20 AI Tutor minutes every day.",
    "description_ar": "٢٠ دقيقة يومياً للتحدث مع AI Tutor.",
    "price_sdg": 100000,
    "ai_tutor_daily_minutes": 20,
    "library_audio_daily_minutes": 50,
    "sort_order": 35,
}


def seed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "SubscriptionPlan")
    Plan.objects.update_or_create(code=PRO_20M["code"], defaults=PRO_20M)


def unseed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "SubscriptionPlan")
    Plan.objects.filter(code=PRO_20M["code"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0013_subscriptionplan_ai_tutor_session_cap_minutes_and_more"),
    ]
    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
