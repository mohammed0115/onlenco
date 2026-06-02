"""Seed default AIModelPricing rows.

These are public OpenAI list prices at time of writing and are a STARTING
POINT only — they are fully editable from Django Admin / the dashboard.
Audio per-minute rates for TTS/realtime are approximations (the endpoints
bill per-character / per-token upstream); operators should reconcile against
the real invoice monthly. Cost is never hardcoded in services — it always
reads these rows.
"""
from decimal import Decimal

from django.db import migrations


PRICES = [
    # (model_name, in/1M, out/1M, audio_in/min, audio_out/min)
    ("gpt-4o-mini", "0.15", "0.60", None, None),
    ("gpt-4o", "2.50", "10.00", None, None),
    ("gpt-4.1-mini", "0.40", "1.60", None, None),
    ("whisper-1", "0", "0", "0.006", None),
    ("tts-1", "0", "0", None, "0.015"),
    ("tts-1-hd", "0", "0", None, "0.030"),
    ("gpt-realtime", "0", "0", "0.060", "0.240"),
    ("gpt-image-1-mini", "0", "0", None, None),
]


def seed(apps, schema_editor):
    AIModelPricing = apps.get_model("ai_usage", "AIModelPricing")
    for name, pin, pout, ain, aout in PRICES:
        AIModelPricing.objects.get_or_create(
            provider="openai", model_name=name, is_active=True,
            effective_to=None,
            defaults=dict(
                input_price_per_1m_tokens=Decimal(pin),
                output_price_per_1m_tokens=Decimal(pout),
                audio_input_price_per_minute=Decimal(ain) if ain is not None else None,
                audio_output_price_per_minute=Decimal(aout) if aout is not None else None,
                currency="USD",
            ),
        )


def unseed(apps, schema_editor):
    AIModelPricing = apps.get_model("ai_usage", "AIModelPricing")
    AIModelPricing.objects.filter(
        provider="openai",
        model_name__in=[p[0] for p in PRICES],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("ai_usage", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
