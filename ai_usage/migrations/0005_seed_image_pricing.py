"""Seed a CONFIGURABLE default per-image price for gpt-image-1-mini.

$0.02/image is a public list-price approximation and a STARTING POINT only —
admins must verify it against the real provider invoice and edit the
AIModelPricing row in Django Admin. Cost is never hardcoded in services.
"""
from decimal import Decimal

from django.db import migrations


def seed(apps, schema_editor):
    AIModelPricing = apps.get_model("ai_usage", "AIModelPricing")
    AIModelPricing.objects.filter(
        provider="openai", model_name="gpt-image-1-mini", is_active=True,
    ).update(image_price_per_generation=Decimal("0.02"), image_pricing_unit="per_image")


def unseed(apps, schema_editor):
    AIModelPricing = apps.get_model("ai_usage", "AIModelPricing")
    AIModelPricing.objects.filter(
        provider="openai", model_name="gpt-image-1-mini",
    ).update(image_price_per_generation=None)


class Migration(migrations.Migration):
    dependencies = [("ai_usage", "0004_aimodelpricing_image_price_per_1k_images_and_more")]
    operations = [migrations.RunPython(seed, unseed)]
