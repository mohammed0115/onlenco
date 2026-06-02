from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from ai_usage import constants as C
from ai_usage.models import (
    AIDailyUsageSummary,
    AIModelPricing,
    AIUsageLog,
    StudentDailyAILimit,
)
from ai_usage.services import usage_logger

from .helpers import make_user


class PricingTests(TestCase):
    def test_ai_model_pricing_active_lookup(self):
        now = timezone.now()
        old = AIModelPricing.objects.create(
            provider="openai", model_name="px", input_price_per_1m_tokens="1",
            output_price_per_1m_tokens="2", effective_from=now - timedelta(days=10),
            effective_to=now - timedelta(days=5),
        )
        current = AIModelPricing.objects.create(
            provider="openai", model_name="px", input_price_per_1m_tokens="3",
            output_price_per_1m_tokens="4", effective_from=now - timedelta(days=4),
        )
        got = AIModelPricing.get_active("openai", "px")
        self.assertEqual(got.pk, current.pk)
        # A point inside the old window resolves to the old row.
        got_old = AIModelPricing.get_active("openai", "px", now - timedelta(days=7))
        self.assertEqual(got_old.pk, old.pk)

    def test_missing_pricing_returns_none(self):
        self.assertIsNone(AIModelPricing.get_active("openai", "does-not-exist"))


class UsageLogTests(TestCase):
    def test_ai_usage_log_created_success(self):
        u = make_user()
        log = usage_logger.log_success(
            user=u, feature=C.FEATURE_AI_TUTOR, model_name="gpt-4o-mini",
            input_tokens=100, output_tokens=50,
        )
        self.assertEqual(log.status, C.STATUS_SUCCESS)
        self.assertEqual(log.total_tokens, 150)
        self.assertGreater(log.estimated_cost_usd, Decimal("0"))

    def test_ai_usage_log_created_failure(self):
        log = usage_logger.log_failure(
            user=None, feature=C.FEATURE_LIBRARY, model_name="gpt-4o-mini",
            error_message="boom",
        )
        self.assertEqual(log.status, C.STATUS_FAILED)
        self.assertEqual(log.role, C.ROLE_SYSTEM)
        self.assertEqual(log.error_message, "boom")

    def test_duplicate_request_id_does_not_double_count(self):
        usage_logger.log_success(feature="other", model_name="gpt-4o-mini",
                                 input_tokens=10, output_tokens=10, request_id="abc")
        usage_logger.log_success(feature="other", model_name="gpt-4o-mini",
                                 input_tokens=20, output_tokens=20, request_id="abc")
        self.assertEqual(AIUsageLog.objects.filter(request_id="abc").count(), 1)
        self.assertEqual(AIUsageLog.objects.get(request_id="abc").total_tokens, 40)

    def test_api_key_never_appears_in_metadata(self):
        log = usage_logger.log_success(
            feature="other", model_name="m",
            metadata={"api_key": "sk-secret", "prompt": "hi", "ok": "yes"},
        )
        self.assertNotIn("api_key", log.metadata)
        self.assertNotIn("prompt", log.metadata)
        self.assertEqual(log.metadata.get("ok"), "yes")


class ConstraintTests(TestCase):
    def test_ai_daily_summary_unique_constraint(self):
        u = make_user()
        AIDailyUsageSummary.objects.create(date=timezone.localdate(), user=u, role="student")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AIDailyUsageSummary.objects.create(date=timezone.localdate(), user=u, role="student")

    def test_student_daily_limit_unique_per_day(self):
        u = make_user()
        StudentDailyAILimit.objects.create(student=u, date=timezone.localdate())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentDailyAILimit.objects.create(student=u, date=timezone.localdate())
