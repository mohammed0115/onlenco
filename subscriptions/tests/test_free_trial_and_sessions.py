"""Sprint 2 tests: free trial grant, session lifecycle, hard-stop, concurrency."""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import AITutorSession, FreeTrialUsage, SubscriptionPlan
from subscriptions.services import quota_service, session_service, subscription_service
from subscriptions.services.session_service import (
    ConcurrentSessionExists, QuotaExhausted,
)


User = get_user_model()


def _make_user(email: str = "u@example.com"):
    return User.objects.create_user(username=email, email=email, password="pw")


class FreeTrialGrantTests(TestCase):
    def test_new_user_receives_300_second_trial_via_signal(self):
        user = _make_user("trial@example.com")
        trial = FreeTrialUsage.objects.get(user=user)
        self.assertEqual(trial.free_seconds_granted, 300)
        self.assertEqual(trial.free_seconds_used, 0)
        self.assertFalse(trial.is_consumed)

    def test_signal_is_idempotent_on_user_resave(self):
        user = _make_user("idem@example.com")
        user.save()  # re-fire post_save
        self.assertEqual(FreeTrialUsage.objects.filter(user=user).count(), 1)

    def test_trial_remaining_helper(self):
        user = _make_user("rem@example.com")
        self.assertEqual(quota_service.get_free_trial_remaining_seconds(user), 300)

    def test_consume_trial_decrements(self):
        user = _make_user("c@example.com")
        remaining = quota_service.consume_free_trial_seconds(user, 100)
        self.assertEqual(remaining, 200)
        remaining = quota_service.consume_free_trial_seconds(user, 200)
        self.assertEqual(remaining, 0)
        trial = FreeTrialUsage.objects.get(user=user)
        self.assertTrue(trial.is_consumed)
        self.assertIsNotNone(trial.consumed_at)

    def test_consume_trial_clamps_at_zero(self):
        user = _make_user("cl@example.com")
        remaining = quota_service.consume_free_trial_seconds(user, 5000)
        self.assertEqual(remaining, 0)


class EffectiveQuotaTests(TestCase):
    def test_no_sub_uses_trial(self):
        user = _make_user("ns@example.com")
        seconds, source = quota_service.effective_ai_tutor_remaining(user)
        self.assertEqual(seconds, 300)
        self.assertEqual(source, "free_trial")

    def test_active_sub_wins_over_trial(self):
        user = _make_user("won@example.com")
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(user=user, plan=plan)
        seconds, source = quota_service.effective_ai_tutor_remaining(user)
        self.assertEqual(seconds, 600)
        self.assertEqual(source, "subscription")

    def test_no_sub_and_consumed_trial_returns_none(self):
        user = _make_user("done@example.com")
        quota_service.consume_free_trial_seconds(user, 300)
        seconds, source = quota_service.effective_ai_tutor_remaining(user)
        self.assertEqual(seconds, 0)
        self.assertEqual(source, "none")

    def test_can_user_start_ai_tutor_now(self):
        user = _make_user("now@example.com")
        self.assertTrue(quota_service.can_user_start_ai_tutor_now(user))
        quota_service.consume_free_trial_seconds(user, 300)
        self.assertFalse(quota_service.can_user_start_ai_tutor_now(user))


class SessionLifecycleTests(TestCase):
    def setUp(self):
        self.user = _make_user("s@example.com")

    def test_start_session_requires_quota(self):
        # Drain the trial first.
        quota_service.consume_free_trial_seconds(self.user, 300)
        with self.assertRaises(QuotaExhausted):
            session_service.start_session(self.user)

    def test_start_session_picks_trial_source_when_no_sub(self):
        session = session_service.start_session(self.user, voice="alloy")
        self.assertEqual(session.status, "in_progress")
        self.assertEqual(session.quota_source, "free_trial")
        self.assertEqual(session.voice, "alloy")

    def test_starting_again_cancels_previous_open_session(self):
        # Updated policy: a fresh Start cancels the previous in_progress
        # row instead of raising. The user can only run one call at a time
        # and we don't want them blocked behind a ghost from a crashed tab.
        first = session_service.start_session(self.user)
        second = session_service.start_session(self.user)
        self.assertNotEqual(first.pk, second.pk)
        first.refresh_from_db()
        self.assertEqual(first.status, "cancelled")
        self.assertEqual(second.status, "in_progress")

    def test_end_session_deducts_from_trial(self):
        session = session_service.start_session(self.user)
        closed = session_service.end_session(session.pk, actual_seconds=120)
        self.assertEqual(closed.status, "completed")
        self.assertEqual(closed.duration_seconds, 120)
        self.assertEqual(closed.consumed_seconds, 120)
        self.assertEqual(closed.remaining_after_seconds, 180)
        trial = FreeTrialUsage.objects.get(user=self.user)
        self.assertEqual(trial.free_seconds_used, 120)

    def test_end_session_deducts_from_subscription_when_present(self):
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(user=self.user, plan=plan)
        session = session_service.start_session(self.user)
        self.assertEqual(session.quota_source, "subscription")
        closed = session_service.end_session(session.pk, actual_seconds=200)
        self.assertEqual(closed.remaining_after_seconds, 400)
        # Trial untouched.
        trial = FreeTrialUsage.objects.get(user=self.user)
        self.assertEqual(trial.free_seconds_used, 0)

    def test_end_session_idempotent(self):
        session = session_service.start_session(self.user)
        session_service.end_session(session.pk, actual_seconds=60)
        # Re-close — should noop, not double-deduct.
        session_service.end_session(session.pk, actual_seconds=60)
        trial = FreeTrialUsage.objects.get(user=self.user)
        self.assertEqual(trial.free_seconds_used, 60)

    def test_killed_by_quota_flag(self):
        session = session_service.start_session(self.user)
        closed = session_service.end_session(
            session.pk, actual_seconds=500, killed_by_quota=True,
        )
        self.assertEqual(closed.status, "killed_quota_exceeded")
        # Consumed seconds clamped to trial limit (300).
        self.assertEqual(closed.consumed_seconds, 500)
        # Trial fully used.
        trial = FreeTrialUsage.objects.get(user=self.user)
        self.assertEqual(trial.free_seconds_used, 300)
        self.assertTrue(trial.is_consumed)

    def test_cancel_session_does_not_deduct(self):
        session = session_service.start_session(self.user)
        session_service.cancel_session(session.pk)
        trial = FreeTrialUsage.objects.get(user=self.user)
        self.assertEqual(trial.free_seconds_used, 0)
        # User can immediately start another since the previous is closed.
        new_session = session_service.start_session(self.user)
        self.assertEqual(new_session.status, "in_progress")


class UpgradePageTests(TestCase):
    def test_upgrade_page_lists_paid_plans_only(self):
        user = _make_user("up@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("subscriptions:upgrade"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "free_trial")
        self.assertContains(response, "basic_10m")
        self.assertContains(response, "pro_30m")

    def test_quota_snapshot_api(self):
        user = _make_user("api@example.com")
        self.client.force_login(user)
        response = self.client.get(reverse("subscriptions:quota_snapshot"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["free_trial"]["remaining_seconds"], 300)
        self.assertEqual(data["ai_tutor"]["limit_seconds"], 0)

    def test_upgrade_page_redirects_anonymous(self):
        response = self.client.get(reverse("subscriptions:upgrade"))
        self.assertEqual(response.status_code, 302)


class DailyResetWithSubscriptionTests(TestCase):
    """Daily quota resets for subscribers; trial does NOT reset."""

    def test_subscription_resets_next_day(self):
        user = _make_user("d1@example.com")
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(user=user, plan=plan)
        quota_service.consume_ai_tutor_seconds(user, 600)
        self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(user), 0)
        tomorrow = timezone.localdate() + timedelta(days=1)
        with patch.object(quota_service, "_today", return_value=tomorrow):
            self.assertEqual(quota_service.get_remaining_ai_tutor_seconds(user), 600)

    def test_trial_does_not_reset_next_day(self):
        user = _make_user("d2@example.com")
        quota_service.consume_free_trial_seconds(user, 300)
        # "Tomorrow" doesn't restore trial.
        self.assertEqual(quota_service.get_free_trial_remaining_seconds(user), 0)
