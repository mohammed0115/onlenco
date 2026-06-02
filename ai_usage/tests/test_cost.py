from decimal import Decimal

from django.test import TestCase

from ai_usage.models import AIModelPricing
from ai_usage.services import cost_calculator as cc


class CostTests(TestCase):
    def setUp(self):
        self.pricing = AIModelPricing.objects.create(
            provider="openai", model_name="costtest",
            input_price_per_1m_tokens="10", output_price_per_1m_tokens="30",
            audio_input_price_per_minute="0.06", audio_output_price_per_minute="0.24",
        )

    def test_token_cost_calculation(self):
        # 1,000,000 in @ $10 + 1,000,000 out @ $30 = $40
        cost = cc.calculate_token_cost("openai", "costtest", 1_000_000, 1_000_000)
        self.assertEqual(cost, Decimal("40.000000"))

    def test_audio_cost_calculation(self):
        # 60s in @ $0.06/min ($0.06) + 120s out @ $0.24/min ($0.48) = $0.54
        cost = cc.calculate_audio_cost("openai", "costtest", 60, 120)
        self.assertEqual(cost, Decimal("0.540000"))

    def test_total_cost_combines(self):
        total = cc.calculate_total_cost(
            "openai", "costtest", input_tokens=1_000_000, output_tokens=0,
            audio_input_seconds=60, audio_output_seconds=0,
        )
        self.assertEqual(total, Decimal("10.060000"))

    def test_missing_pricing_returns_zero_and_warning(self):
        with self.assertLogs("ai_usage.services.cost_calculator", level="WARNING"):
            cost = cc.calculate_token_cost("openai", "nope", 1000, 1000)
        self.assertEqual(cost, Decimal("0"))

    def test_decimal_precision(self):
        cost = cc.calculate_token_cost("openai", "costtest", 1, 1)
        self.assertIsInstance(cost, Decimal)
        # 1/1e6*10 + 1/1e6*30 = 0.00004
        self.assertEqual(cost, Decimal("0.000040"))

    def test_safe_decimal_never_raises(self):
        self.assertEqual(cc.safe_decimal("garbage"), Decimal("0"))
        self.assertEqual(cc.safe_decimal(None), Decimal("0"))
        self.assertEqual(cc.safe_decimal(1.5), Decimal("1.5"))
