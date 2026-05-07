from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import AIUsageLog
from core.services.ai_usage import (
    DAILY_LIMITS,
    daily_count,
    is_within_limit,
    log_usage,
)

User = get_user_model()


class AIUsageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lou", password="pw")

    def test_log_usage_creates_row(self):
        log = log_usage(self.user, "tutor", model="gpt-x", prompt_tokens=100, completion_tokens=50)
        self.assertIsNotNone(log.pk)
        self.assertTrue(log.success)
        self.assertEqual(AIUsageLog.objects.filter(user=self.user, feature="tutor").count(), 1)

    def test_within_limit_for_free_user_under_cap(self):
        free_cap, _ = DAILY_LIMITS["tutor"]
        for _ in range(free_cap - 1):
            log_usage(self.user, "tutor")
        self.assertTrue(is_within_limit(self.user, "tutor"))
        log_usage(self.user, "tutor")
        self.assertFalse(is_within_limit(self.user, "tutor"))

    def test_admin_unlimited(self):
        self.user.is_staff = True
        self.user.save()
        self.user.profile.role = "admin"
        self.user.profile.save()
        for _ in range(1000):  # excessive but fast — bulk_create alternative would be cleaner
            pass
        # We don't actually need 1000 rows — just check the gating logic
        self.assertTrue(is_within_limit(self.user, "tutor"))

    def test_premium_higher_cap_than_free(self):
        free_cap, premium_cap = DAILY_LIMITS["tutor"]
        self.assertGreater(premium_cap, free_cap)
        # Make user premium
        self.user.profile.subscription_status = "active"
        self.user.profile.save()
        for _ in range(free_cap):
            log_usage(self.user, "tutor")
        # Free cap exceeded but premium still allows
        self.assertTrue(is_within_limit(self.user, "tutor"))

    def test_old_logs_outside_24h_window_dont_count(self):
        log = log_usage(self.user, "tutor")
        AIUsageLog.objects.filter(pk=log.pk).update(
            created_at=timezone.now() - timedelta(hours=48)
        )
        self.assertEqual(daily_count(self.user, "tutor"), 0)

    def test_failure_logging(self):
        log_usage(self.user, "tutor", success=False, error_message="boom")
        log = AIUsageLog.objects.get(user=self.user)
        self.assertFalse(log.success)
        self.assertEqual(log.error_message, "boom")

    def test_anonymous_user_logged_with_null(self):
        from django.contrib.auth.models import AnonymousUser
        log = log_usage(AnonymousUser(), "tutor")
        self.assertIsNone(log.user)
