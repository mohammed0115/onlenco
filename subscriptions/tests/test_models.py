from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from subscriptions.models import SubscriptionPlan, UserDailyQuota, UserSubscription


User = get_user_model()


class SubscriptionPlanSeedTests(TestCase):
    def test_initial_plans_seeded(self):
        codes = set(SubscriptionPlan.objects.values_list("code", flat=True))
        self.assertSetEqual(codes, {"free_trial", "starter_5m", "basic_10m", "plus_15m", "pro_30m"})

    def test_free_trial_flag_set(self):
        trial = SubscriptionPlan.objects.get(code="free_trial")
        self.assertTrue(trial.is_free_trial)
        self.assertEqual(trial.ai_tutor_daily_minutes, 5)
        self.assertEqual(trial.price_sdg, 0)

    def test_paid_plans_have_prices_and_minutes(self):
        basic = SubscriptionPlan.objects.get(code="basic_10m")
        self.assertEqual(basic.ai_tutor_daily_minutes, 10)
        self.assertEqual(basic.price_sdg, 50000)
        self.assertFalse(basic.is_free_trial)


class UserSubscriptionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u@example.com", email="u@example.com", password="pw")
        self.plan = SubscriptionPlan.objects.get(code="basic_10m")

    def test_active_subscription_is_currently_active(self):
        now = timezone.now()
        sub = UserSubscription.objects.create(
            user=self.user, plan=self.plan, status="active",
            start_date=now, end_date=now + timedelta(days=30),
        )
        self.assertTrue(sub.is_currently_active)

    def test_expired_end_date_is_not_active(self):
        now = timezone.now()
        sub = UserSubscription.objects.create(
            user=self.user, plan=self.plan, status="active",
            start_date=now - timedelta(days=60),
            end_date=now - timedelta(days=1),
        )
        self.assertFalse(sub.is_currently_active)

    def test_pending_status_is_not_active(self):
        sub = UserSubscription.objects.create(
            user=self.user, plan=self.plan, status="pending",
            start_date=timezone.now(),
        )
        self.assertFalse(sub.is_currently_active)


class UserDailyQuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="q@example.com", email="q@example.com", password="pw")

    def test_unique_per_user_per_day(self):
        today = timezone.localdate()
        UserDailyQuota.objects.create(user=self.user, date=today)
        with self.assertRaises(IntegrityError):
            UserDailyQuota.objects.create(user=self.user, date=today)
