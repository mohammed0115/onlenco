"""Tests for the 'subscribed-but-no-plan' fix (plan reconciliation).

Covers default_subscription_plan, the reconcile_subscription_plans command,
and extend_subscription keeping the plan-based quota in sync with the access
flag (so a 'subscribed' user never silently gets 0 minutes).
"""
from __future__ import annotations

from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from subscriptions.models import SubscriptionPlan, UserSubscription
from subscriptions.services import subscription_service

User = get_user_model()


def _plan(code, *, price, lib=15, free_trial=False):
    return SubscriptionPlan.objects.create(
        code=code, name_en=code, name_ar=code, price_sdg=price,
        ai_tutor_daily_minutes=2, library_audio_daily_minutes=lib,
        is_active=True, is_free_trial=free_trial,
    )


def _subscribed_user(email, *, days=30):
    u = User.objects.create_user(username=email, email=email, password="pw")
    u.profile.subscription_status = "active"
    u.profile.subscription_expires_at = timezone.now() + timedelta(days=days)
    u.profile.save(update_fields=["subscription_status", "subscription_expires_at"])
    return u


class DefaultPlanTests(TestCase):
    def setUp(self):
        # Wipe seeded plans so the heuristic is deterministic.
        SubscriptionPlan.objects.all().delete()
        self.free = _plan("free_x", price=0, lib=5, free_trial=True)
        self.cheap = _plan("cheap_x", price=100, lib=10)
        self.mid = _plan("mid_x", price=500, lib=30)

    def test_default_is_cheapest_paid_non_trial(self):
        self.assertEqual(subscription_service.default_subscription_plan(), self.cheap)

    @override_settings(DEFAULT_SUBSCRIPTION_PLAN_CODE="mid_x")
    def test_settings_code_wins(self):
        self.assertEqual(subscription_service.default_subscription_plan(), self.mid)

    def test_returns_any_active_when_only_free(self):
        self.cheap.delete()
        self.mid.delete()
        self.assertEqual(subscription_service.default_subscription_plan(), self.free)


class ReconcileCommandTests(TestCase):
    def setUp(self):
        SubscriptionPlan.objects.all().delete()
        self.plan = _plan("recon_basic", price=25000, lib=15)
        self.gap_user = _subscribed_user("gap@example.com")          # active flag, no plan
        self.ok_user = _subscribed_user("ok@example.com")            # active flag + plan
        subscription_service.activate_subscription(user=self.ok_user, plan=self.plan, duration_days=30)
        self.free_user = User.objects.create_user(                   # not subscribed at all
            username="free@example.com", email="free@example.com", password="pw")

    def _run(self, *args):
        out = StringIO()
        call_command("reconcile_subscription_plans", *args, stdout=out)
        return out.getvalue()

    def test_dry_run_writes_nothing(self):
        self._run("--dry-run")
        self.assertIsNone(subscription_service.active_subscription_for(self.gap_user))

    def test_apply_grants_plan_to_gap_user(self):
        self._run("--apply")
        sub = subscription_service.active_subscription_for(self.gap_user)
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan, self.plan)

    def test_apply_does_not_duplicate_for_ok_user(self):
        before = UserSubscription.objects.filter(user=self.ok_user).count()
        self._run("--apply")
        self.assertEqual(UserSubscription.objects.filter(user=self.ok_user).count(), before)

    def test_apply_skips_non_subscribed(self):
        self._run("--apply")
        self.assertIsNone(subscription_service.active_subscription_for(self.free_user))


class ExtendSubscriptionSyncTests(TestCase):
    def setUp(self):
        SubscriptionPlan.objects.all().delete()
        self.default = _plan("def_plan", price=25000, lib=15)
        self.other = _plan("other_plan", price=99000, lib=60)
        self.rf = RequestFactory()

    def _request(self):
        req = self.rf.post("/admin/extend/")
        req.user = AnonymousUser()
        return req

    def test_extend_attaches_plan_when_user_had_none(self):
        from platform_admin.services import payment_review_service
        u = _subscribed_user("noplan@example.com")
        self.assertIsNone(subscription_service.active_subscription_for(u))
        payment_review_service.extend_subscription(self._request(), u, 30)
        sub = subscription_service.active_subscription_for(u)
        self.assertIsNotNone(sub)            # plan-based quota now works
        self.assertEqual(sub.plan, self.default)

    def test_extend_keeps_existing_plan(self):
        from platform_admin.services import payment_review_service
        u = _subscribed_user("hasplan@example.com")
        subscription_service.activate_subscription(user=u, plan=self.other, duration_days=10)
        payment_review_service.extend_subscription(self._request(), u, 30)
        sub = subscription_service.active_subscription_for(u)
        self.assertEqual(sub.plan, self.other)  # not switched to default
