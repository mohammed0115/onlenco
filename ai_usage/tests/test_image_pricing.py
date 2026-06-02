"""Prompt 16.5 — image pricing + reconciliation tests."""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ai_usage import constants as C
from ai_usage.models import AIModelPricing, AIUsageLog
from ai_usage.services import cost_calculator as cc
from ai_usage.services import usage_logger


class ImagePricingTests(TestCase):
    def setUp(self):
        # Seeded by migration 0005, but set explicitly for isolation.
        AIModelPricing.objects.update_or_create(
            provider="openai", model_name="gpt-image-1-mini", effective_to=None,
            defaults={"image_price_per_generation": Decimal("0.02"),
                      "image_pricing_unit": "per_image", "is_active": True},
        )

    def test_image_pricing_lookup(self):
        self.assertEqual(cc.calculate_image_cost("openai", "gpt-image-1-mini", 1),
                         Decimal("0.020000"))
        self.assertEqual(cc.calculate_image_cost("openai", "gpt-image-1-mini", 3),
                         Decimal("0.060000"))

    def test_image_generation_cost_nonzero_when_pricing_exists(self):
        # usage_logger doesn't auto-price images; the wrapper passes the cost.
        cost = cc.calculate_image_cost("openai", "gpt-image-1-mini", 1)
        log = usage_logger.log_success(feature=C.FEATURE_MEDIA_GENERATION,
                                       model_name="gpt-image-1-mini",
                                       estimated_cost_usd=cost)
        self.assertEqual(log.estimated_cost_usd, Decimal("0.020000"))

    def test_missing_image_pricing_zero_with_warning(self):
        with self.assertLogs("ai_usage.services.cost_calculator", level="WARNING"):
            cost = cc.calculate_image_cost("openai", "no-such-image-model", 1)
        self.assertEqual(cost, Decimal("0"))

    def test_per_1k_images_unit(self):
        AIModelPricing.objects.create(
            provider="openai", model_name="img-bulk",
            image_price_per_1k_images=Decimal("20"), image_pricing_unit="per_1k_images")
        self.assertEqual(cc.calculate_image_cost("openai", "img-bulk", 1000), Decimal("20.000000"))

    def test_audio_pricing_still_works(self):
        AIModelPricing.objects.create(provider="openai", model_name="tts-x",
                                      audio_output_price_per_minute=Decimal("0.015"))
        # 60s out → $0.015
        self.assertEqual(cc.calculate_audio_cost("openai", "tts-x", 0, 60), Decimal("0.015000"))

    def test_token_pricing_still_works(self):
        AIModelPricing.objects.create(provider="openai", model_name="tok-x",
                                      input_price_per_1m_tokens=Decimal("10"),
                                      output_price_per_1m_tokens=Decimal("30"))
        self.assertEqual(cc.calculate_token_cost("openai", "tok-x", 1_000_000, 0), Decimal("10.000000"))


class ReconcileImageCostTests(TestCase):
    def setUp(self):
        AIModelPricing.objects.update_or_create(
            provider="openai", model_name="gpt-image-1-mini", effective_to=None,
            defaults={"image_price_per_generation": Decimal("0.02"),
                      "image_pricing_unit": "per_image", "is_active": True})
        # A historical $0 image log (as Prompt 16 created) + an audio log.
        self.img = AIUsageLog.objects.create(
            feature=C.FEATURE_MEDIA_GENERATION, provider="openai",
            model_name="gpt-image-1-mini", status=C.STATUS_SUCCESS,
            estimated_cost_usd=Decimal("0"), metadata={"image_count": 1})
        self.aud = AIUsageLog.objects.create(
            feature=C.FEATURE_TTS, provider="openai", model_name="tts-1",
            status=C.STATUS_SUCCESS, estimated_cost_usd=Decimal("0.002"),
            audio_output_seconds=8)

    def test_reconcile_image_ai_usage_costs_dry_run(self):
        call_command("reconcile_image_ai_usage_costs", "--dry-run", stdout=StringIO())
        self.img.refresh_from_db()
        self.assertEqual(self.img.estimated_cost_usd, Decimal("0"))  # unchanged

    def test_reconcile_image_ai_usage_costs_confirm(self):
        call_command("reconcile_image_ai_usage_costs", "--confirm", stdout=StringIO())
        self.img.refresh_from_db()
        self.assertEqual(self.img.estimated_cost_usd, Decimal("0.020000"))
        self.assertTrue(self.img.metadata.get("image_cost_recalculated_after_prompt_16_5"))

    def test_reconcile_does_not_touch_audio_or_text_logs(self):
        call_command("reconcile_image_ai_usage_costs", "--confirm", stdout=StringIO())
        self.aud.refresh_from_db()
        self.assertEqual(self.aud.estimated_cost_usd, Decimal("0.002"))
