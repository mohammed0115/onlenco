"""Focused 18.5B hardening tests.

Locks the guarantees from Prompt 18.5B:
  * the payment amount + duration come from the server-side catalog, never
    from the client;
  * the 20-minute upgrade tier exists at 100,000 SDG;
  * admin-edited AI-Tutor / Library minutes are read live from the active
    plan (no parallel constants);
  * the manual payment lifecycle (pending → approved → refunded/expired)
    drives course access correctly.
"""
from __future__ import annotations

from datetime import timedelta
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone

from courses.services.student_flow import can_access_course
from payments.forms import PaymentSubmissionForm
from payments.models import PLAN_DETAILS, PaymentMethodAccount, PaymentSubmission
from subscriptions.models import SubscriptionPlan, UserSubscription
from subscriptions.services import quota_service, subscription_service


User = get_user_model()


def _png() -> SimpleUploadedFile:
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
    return SimpleUploadedFile("proof.png", buf.getvalue(), content_type="image/png")


class _NonFreeCourse:
    """Lightweight stand-in: ``can_access_course`` only reads ``is_free``."""
    is_free = False


class _FreeCourse:
    is_free = True


# ---------------------------------------------------------------------------
# A) Catalog is the server-side source of truth for amount + duration
# ---------------------------------------------------------------------------
class CatalogSourceOfTruthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cat@x.com", email="cat@x.com", password="pw")
        PaymentMethodAccount.objects.filter(method="bankak").update(is_active=True)

    def test_frontend_cannot_override_payment_amount(self):
        """A bogus amount in the POST is ignored — the server uses PLAN_DETAILS."""
        form = PaymentSubmissionForm(
            data={
                "plan": "monthly", "method": "bankak",
                "transaction_reference": "x", "amount_sdg": 1,  # attacker value
            },
            files={"screenshot": _png()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        submission = form.save(user=self.user)
        self.assertEqual(submission.amount_sdg, PLAN_DETAILS["monthly"]["price_sdg"])
        self.assertEqual(submission.amount_sdg, 30000)

    def test_quarterly_amount_from_catalog(self):
        form = PaymentSubmissionForm(
            data={"plan": "quarterly", "method": "bankak", "transaction_reference": "x"},
            files={"screenshot": _png()},
        )
        self.assertTrue(form.is_valid(), form.errors)
        submission = form.save(user=self.user)
        self.assertEqual(submission.amount_sdg, 50000)


class PaymentDurationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dur@x.com", email="dur@x.com", password="pw")
        self.reviewer = User.objects.create_user(
            username="durrev@x.com", email="durrev@x.com", password="pw", is_staff=True,
        )

    def _submit(self, plan: str) -> PaymentSubmission:
        return PaymentSubmission.objects.create(
            user=self.user, plan=plan, method="bankak",
            amount_sdg=PLAN_DETAILS[plan]["price_sdg"],
            screenshot=_png(), status="pending",
        )

    def test_monthly_activates_30_day_subscription(self):
        self._submit("monthly").approve(self.reviewer)
        sub = UserSubscription.objects.get(user=self.user, status="active")
        self.assertGreaterEqual((sub.end_date - sub.start_date).days, 29)
        self.assertLessEqual((sub.end_date - sub.start_date).days, 31)

    def test_quarterly_activates_90_day_subscription(self):
        self._submit("quarterly").approve(self.reviewer)
        sub = UserSubscription.objects.get(user=self.user, status="active")
        self.assertGreaterEqual((sub.end_date - sub.start_date).days, 89)


# ---------------------------------------------------------------------------
# B) 20-minute tier + admin-editable plan fields
# ---------------------------------------------------------------------------
class TwentyMinuteTierTests(TestCase):
    def test_pro_20m_plan_seeded(self):
        plan = SubscriptionPlan.objects.get(code="pro_20m")
        self.assertEqual(plan.price_sdg, 100000)
        self.assertEqual(plan.ai_tutor_daily_minutes, 20)
        self.assertTrue(plan.is_active)

    def test_upgrade_grid_matches_product_rules(self):
        grid = dict(
            SubscriptionPlan.objects.filter(
                code__in=["basic_10m", "pro_20m", "pro_30m"],
            ).values_list("ai_tutor_daily_minutes", "price_sdg")
        )
        self.assertEqual(grid[10], 50000)
        self.assertEqual(grid[20], 100000)
        self.assertEqual(grid[30], 150000)

    def test_new_plan_fields_exist_and_default_safe(self):
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        # New additive fields exist and keep prior behaviour (cap 0 = fallback).
        self.assertEqual(plan.ai_tutor_session_cap_minutes, 0)
        self.assertEqual(plan.library_session_cap_minutes, 0)
        self.assertTrue(plan.course_access_enabled)
        self.assertTrue(plan.daily_quiz_enabled)
        self.assertTrue(plan.placement_enabled)
        # Naming-parity aliases.
        self.assertEqual(plan.ai_tutor_daily_cap_minutes, plan.ai_tutor_daily_minutes)
        self.assertEqual(plan.library_daily_minutes, plan.library_audio_daily_minutes)


# ---------------------------------------------------------------------------
# C) Plan edits reflect immediately in the usage service
# ---------------------------------------------------------------------------
class PlanReflectsImmediatelyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ref@x.com", email="ref@x.com", password="pw")
        self.plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(
            user=self.user, plan=self.plan, duration_days=30,
        )

    def test_ai_minutes_edit_is_read_live(self):
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 600)  # 10 min
        # Admin lowers the allowance.
        self.plan.ai_tutor_daily_minutes = 2
        self.plan.save(update_fields=["ai_tutor_daily_minutes"])
        self.assertEqual(quota_service.daily_ai_tutor_limit_seconds(self.user), 120)  # 2 min

    def test_library_minutes_read_from_plan(self):
        self.plan.library_audio_daily_minutes = 7
        self.plan.save(update_fields=["library_audio_daily_minutes"])
        self.assertEqual(quota_service.daily_library_limit_seconds(self.user), 420)  # 7 min

    @override_settings(AI_REALTIME_MAX_SESSION_SECONDS=900)
    def test_session_cap_falls_back_to_setting_when_unset(self):
        self.assertEqual(quota_service.ai_tutor_session_cap_seconds(self.user), 900)

    @override_settings(AI_REALTIME_MAX_SESSION_SECONDS=900)
    def test_session_cap_uses_plan_value_when_set(self):
        self.plan.ai_tutor_session_cap_minutes = 3
        self.plan.save(update_fields=["ai_tutor_session_cap_minutes"])
        self.assertEqual(quota_service.ai_tutor_session_cap_seconds(self.user), 180)

    def test_inactive_plan_not_offered_for_purchase(self):
        SubscriptionPlan.objects.filter(code="pro_20m").update(is_active=False)
        purchasable = set(
            SubscriptionPlan.objects.filter(is_active=True, is_free_trial=False)
            .values_list("code", flat=True)
        )
        self.assertNotIn("pro_20m", purchasable)
        self.assertIn("basic_10m", purchasable)


# ---------------------------------------------------------------------------
# E) Access control across the payment lifecycle
# ---------------------------------------------------------------------------
class AccessControlLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="acc@x.com", email="acc@x.com", password="pw")
        self.reviewer = User.objects.create_user(
            username="accrev@x.com", email="accrev@x.com", password="pw", is_staff=True,
        )

    def _submit(self, plan="monthly") -> PaymentSubmission:
        return PaymentSubmission.objects.create(
            user=self.user, plan=plan, method="bankak",
            amount_sdg=PLAN_DETAILS[plan]["price_sdg"],
            screenshot=_png(), status="pending",
        )

    def test_no_subscription_blocks_paid_course(self):
        self.assertFalse(can_access_course(self.user, _NonFreeCourse()))

    def test_free_course_always_open(self):
        self.assertTrue(can_access_course(self.user, _FreeCourse()))

    def test_pending_payment_blocks_paid_course(self):
        self._submit()
        self.user.profile.subscription_status = "pending"
        self.user.profile.save(update_fields=["subscription_status"])
        self.assertFalse(can_access_course(self.user, _NonFreeCourse()))

    def test_approved_payment_grants_paid_course(self):
        self._submit().approve(self.reviewer)
        self.user.profile.refresh_from_db()
        self.assertTrue(can_access_course(self.user, _NonFreeCourse()))

    def test_refunded_payment_blocks_paid_course(self):
        payment = self._submit()
        payment.approve(self.reviewer)
        payment.refund(reviewer=self.reviewer, reason="duplicate")
        self.user.profile.refresh_from_db()
        self.assertFalse(can_access_course(self.user, _NonFreeCourse()))

    def test_expired_subscription_blocks_paid_course(self):
        self._submit().approve(self.reviewer)
        profile = self.user.profile
        profile.refresh_from_db()
        # Force expiry in the past.
        profile.subscription_expires_at = timezone.now() - timedelta(days=1)
        profile.save(update_fields=["subscription_expires_at"])
        self.assertFalse(can_access_course(self.user, _NonFreeCourse()))
