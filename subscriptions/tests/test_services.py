from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from subscriptions.models import SubscriptionPlan, UserDailyQuota, UserSubscription
from subscriptions.services import quota_service, subscription_service


User = get_user_model()


class QuotaServiceWithoutSubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ns@example.com", email="ns@example.com", password="pw")

    def test_no_subscription_means_zero_limit(self):
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 0)
        self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(self.user), 0)
        self.assertFalse(quota_service.can_user_start_ai_tutor(self.user))

    def test_consume_without_subscription_is_noop(self):
        result = quota_service.consume_ai_tutor_seconds(self.user, 60)
        self.assertEqual(result, 0)
        self.assertFalse(UserDailyQuota.objects.filter(user=self.user).exists())


class QuotaServiceWithSubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="s@example.com", email="s@example.com", password="pw")
        self.plan = SubscriptionPlan.objects.get(code="basic_10m")  # 10 min/day
        subscription_service.activate_subscription(user=self.user, plan=self.plan, duration_days=30)

    def test_initial_remaining_equals_plan_limit(self):
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 600)
        self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(self.user), 600)
        self.assertTrue(quota_service.can_user_start_ai_tutor(self.user))

    def test_consume_decrements_remaining(self):
        remaining = quota_service.consume_ai_tutor_seconds(self.user, 200)
        self.assertEqual(remaining, 400)
        # Second consume same day accumulates
        remaining = quota_service.consume_ai_tutor_seconds(self.user, 100)
        self.assertEqual(remaining, 300)

    def test_consume_clamps_at_limit(self):
        remaining = quota_service.consume_ai_tutor_seconds(self.user, 5000)
        self.assertEqual(remaining, 0)
        self.assertFalse(quota_service.can_user_start_ai_tutor(self.user))

    def test_new_day_resets_quota(self):
        quota_service.consume_ai_tutor_seconds(self.user, 600)
        self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(self.user), 0)
        # Simulate tomorrow
        tomorrow = timezone.localdate() + timedelta(days=1)
        with patch.object(quota_service, "_today", return_value=tomorrow):
            self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(self.user), 600)
            self.assertTrue(quota_service.can_user_start_ai_tutor(self.user))

    def test_library_quota_independent_of_tutor(self):
        quota_service.consume_ai_tutor_seconds(self.user, 600)  # fully spend tutor
        # Library quota still intact (basic plan: 30 min)
        self.assertEqual(quota_service.get_remaining_library_seconds(self.user), 1800)

    def test_quota_snapshot_shape(self):
        quota_service.consume_ai_tutor_seconds(self.user, 60)
        snap = quota_service.quota_snapshot(self.user)
        self.assertEqual(snap["plan_code"], "basic_10m")
        self.assertEqual(snap["ai_tutor"]["limit_seconds"], 600)
        self.assertEqual(snap["ai_tutor"]["used_seconds"], 60)
        self.assertEqual(snap["ai_tutor"]["remaining_seconds"], 540)


class SubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sub@example.com", email="sub@example.com", password="pw")
        self.basic = SubscriptionPlan.objects.get(code="basic_10m")
        self.plus = SubscriptionPlan.objects.get(code="plus_15m")

    def test_activate_creates_subscription(self):
        sub = subscription_service.activate_subscription(user=self.user, plan=self.basic, duration_days=30)
        self.assertEqual(sub.status, "active")
        self.assertEqual(subscription_service.active_plan_for(self.user).code, "basic_10m")

    def test_same_plan_renewal_extends_end_date(self):
        first = subscription_service.activate_subscription(user=self.user, plan=self.basic, duration_days=30)
        first_end = first.end_date
        renewed = subscription_service.activate_subscription(user=self.user, plan=self.basic, duration_days=30)
        self.assertEqual(renewed.pk, first.pk)
        self.assertGreater(renewed.end_date, first_end)

    def test_upgrade_to_different_plan_replaces_active_row(self):
        first = subscription_service.activate_subscription(user=self.user, plan=self.basic, duration_days=30)
        upgraded = subscription_service.activate_subscription(user=self.user, plan=self.plus, duration_days=30)
        self.assertNotEqual(upgraded.pk, first.pk)
        first.refresh_from_db()
        self.assertEqual(first.status, "expired")
        self.assertEqual(subscription_service.active_plan_for(self.user).code, "plus_15m")

    def test_upgrade_changes_daily_quota(self):
        subscription_service.activate_subscription(user=self.user, plan=self.basic, duration_days=30)
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 600)
        subscription_service.activate_subscription(user=self.user, plan=self.plus, duration_days=30)
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 900)

    def test_cancel_subscription(self):
        sub = subscription_service.activate_subscription(user=self.user, plan=self.basic, duration_days=30)
        subscription_service.cancel_subscription(sub)
        sub.refresh_from_db()
        self.assertEqual(sub.status, "cancelled")
        self.assertIsNone(subscription_service.active_subscription_for(self.user))

    def test_expire_overdue(self):
        now = timezone.now()
        UserSubscription.objects.create(
            user=self.user, plan=self.basic, status="active",
            start_date=now - timedelta(days=40),
            end_date=now - timedelta(days=1),
        )
        UserSubscription.objects.create(
            user=self.user, plan=self.plus, status="active",
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=25),
        )
        flipped = subscription_service.expire_overdue_subscriptions()
        self.assertEqual(flipped, 1)
        actives = UserSubscription.objects.filter(user=self.user, status="active").count()
        self.assertEqual(actives, 1)
