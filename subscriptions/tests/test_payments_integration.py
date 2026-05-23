"""Locks the seam between payments.PaymentSubmission.approve() and the
new subscriptions.UserSubscription / SubscriptionPlan layer."""
from __future__ import annotations

from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone

from payments.models import PaymentSubmission
from subscriptions.models import SubscriptionPlan, UserSubscription


User = get_user_model()


def _png_bytes() -> bytes:
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _make_submission(user, *, plan: str = "monthly") -> PaymentSubmission:
    return PaymentSubmission.objects.create(
        user=user,
        plan=plan,
        method="bankak",
        amount_sdg=30000 if plan == "monthly" else 50000,
        screenshot=SimpleUploadedFile("proof.png", _png_bytes(), content_type="image/png"),
        status="pending",
    )


class PaymentsToSubscriptionsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="p@example.com", email="p@example.com", password="pw")
        self.reviewer = User.objects.create_user(
            username="rev@example.com", email="rev@example.com",
            password="pw", is_staff=True,
        )

    def test_approving_monthly_creates_basic_10m_subscription(self):
        payment = _make_submission(self.user, plan="monthly")
        payment.approve(self.reviewer)
        sub = UserSubscription.objects.filter(user=self.user, status="active").first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan.code, "basic_10m")
        # Legacy field still updated.
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.subscription_status, "active")

    def test_approving_quarterly_links_to_new_plan_with_90_days(self):
        payment = _make_submission(self.user, plan="quarterly")
        payment.approve(self.reviewer)
        sub = UserSubscription.objects.filter(user=self.user, status="active").first()
        self.assertIsNotNone(sub)
        # 90-day duration → end_date is ~90 days from start_date.
        self.assertGreater((sub.end_date - sub.start_date).days, 80)

    def test_approve_persists_payment_link(self):
        payment = _make_submission(self.user)
        payment.approve(self.reviewer)
        sub = UserSubscription.objects.get(user=self.user, status="active")
        self.assertEqual(sub.payment_id, payment.pk)

    def test_second_approve_extends_existing_subscription(self):
        a = _make_submission(self.user, plan="monthly")
        a.approve(self.reviewer)
        sub_first = UserSubscription.objects.get(user=self.user, status="active")
        first_end = sub_first.end_date

        b = _make_submission(self.user, plan="monthly")
        b.approve(self.reviewer)

        # Same row, extended.
        self.assertEqual(UserSubscription.objects.filter(user=self.user, status="active").count(), 1)
        sub_first.refresh_from_db()
        self.assertGreater(sub_first.end_date, first_end)

    def test_approve_is_safe_when_plan_mapping_missing(self):
        """If admin deactivates the mapped plan, approve must still succeed."""
        SubscriptionPlan.objects.filter(code="basic_10m").update(is_active=False)
        payment = _make_submission(self.user, plan="monthly")
        payment.approve(self.reviewer)
        # Payment approval succeeded (legacy fields updated)…
        payment.refresh_from_db()
        self.assertEqual(payment.status, "approved")
        # …but no UserSubscription was created (graceful no-op).
        self.assertFalse(UserSubscription.objects.filter(user=self.user, status="active").exists())


class EntitlementLifecycleTests(TestCase):
    """The four explicit MVP guarantees on payment → AI Tutor entitlement.

    These tests are named exactly as the MVP checklist demands so a
    later grep ``grep -r 'test_payment_approval_'`` finds them.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="ent@example.com", email="ent@example.com", password="pw",
        )
        self.reviewer = User.objects.create_user(
            username="ent_rev@example.com", email="ent_rev@example.com",
            password="pw", is_staff=True,
        )

    def test_payment_approval_activates_subscription_entitlement(self):
        """Approving a monthly payment creates an *active* UserSubscription
        bound to ``basic_10m`` (the new-style plan code)."""
        payment = _make_submission(self.user, plan="monthly")
        payment.approve(self.reviewer)
        sub = UserSubscription.objects.filter(user=self.user, status="active").first()
        self.assertIsNotNone(sub)
        self.assertEqual(sub.plan.code, "basic_10m")
        self.assertEqual(sub.payment_id, payment.pk)

    def test_payment_approval_unlocks_ai_tutor_minutes(self):
        """After approval, ``effective_ai_tutor_remaining`` returns the full
        daily allowance from the plan (10 min == 600 seconds)."""
        from subscriptions.services.quota_service import effective_ai_tutor_remaining
        payment = _make_submission(self.user, plan="monthly")
        payment.approve(self.reviewer)
        seconds, source = effective_ai_tutor_remaining(self.user)
        self.assertGreater(seconds, 0)
        self.assertEqual(source, "subscription")
        # basic_10m → 10 minutes/day → 600 seconds.
        self.assertEqual(seconds, 600)

    def test_duplicate_payment_approval_is_idempotent(self):
        """Calling ``approve()`` twice on the same submission must not
        spawn a second UserSubscription nor extend the existing one."""
        payment = _make_submission(self.user, plan="monthly")
        payment.approve(self.reviewer)
        sub_first = UserSubscription.objects.get(user=self.user, status="active")
        end_after_first = sub_first.end_date
        sub_count_after_first = UserSubscription.objects.filter(user=self.user).count()

        # Second approve on the SAME row.
        payment.approve(self.reviewer)
        sub_first.refresh_from_db()
        self.assertEqual(sub_first.end_date, end_after_first)
        self.assertEqual(
            UserSubscription.objects.filter(user=self.user).count(),
            sub_count_after_first,
        )

    def test_refund_or_expire_removes_or_disables_entitlement(self):
        """A refund must expire the UserSubscription row the payment
        unlocked, dropping ``effective_ai_tutor_remaining`` back to 0."""
        from subscriptions.services.quota_service import effective_ai_tutor_remaining
        payment = _make_submission(self.user, plan="monthly")
        payment.approve(self.reviewer)
        # Sanity: user has paid minutes right after approve.
        seconds, source = effective_ai_tutor_remaining(self.user)
        self.assertGreater(seconds, 0)
        self.assertEqual(source, "subscription")

        # Refund.
        payment.refund(reviewer=self.reviewer, reason="duplicate")

        # The UserSubscription row tied to this payment is now expired.
        self.assertFalse(
            UserSubscription.objects.filter(
                user=self.user, payment=payment, status="active",
            ).exists()
        )
        # And the AI-Tutor quota is back to zero (or free-trial only).
        seconds_after, source_after = effective_ai_tutor_remaining(self.user)
        self.assertNotEqual(source_after, "subscription")
        # Legacy profile field also flipped.
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.subscription_status, "expired")
