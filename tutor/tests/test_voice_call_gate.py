"""Voice-call page gate — quota-aware access tests.

The asymmetry that motivated this file: the API
(``tutor.api.views.voice_call_session``) uses
``effective_ai_tutor_remaining`` (subscription OR free trial), but the
HTML pages ``voice_call_quick`` / ``voice_call_page`` were gated on
``profile.is_subscribed`` alone — locking free-trial students out of
the page their API request would have succeeded on. These tests pin
the corrected, unified rule.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import (
    FreeTrialUsage, SubscriptionPlan, UserSubscription,
)
from subscriptions.services import subscription_service
from tutor.models import TutorConversation


User = get_user_model()


def _grant_subscription(user, *, plan_code: str = "basic_10m", days: int = 30):
    """Set up an active UserSubscription on the given plan."""
    plan = SubscriptionPlan.objects.get(code=plan_code)
    subscription_service.activate_subscription(
        user=user, plan=plan, duration_days=days,
    )
    prof = user.profile
    prof.subscription_status = "active"
    prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=days)
    prof.save()


def _exhaust_free_trial(user):
    """Force the user's free trial to fully consumed."""
    trial, _ = FreeTrialUsage.objects.get_or_create(
        user=user,
        defaults={"free_seconds_granted": 5 * 60},
    )
    trial.free_seconds_used = trial.free_seconds_granted
    trial.is_consumed = True
    trial.consumed_at = timezone.now()
    trial.save()


@override_settings(AXES_ENABLED=False)
class VoiceCallGateTests(TestCase):
    """Contracts the AI Tutor voice-call entry pages must satisfy."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="gate@example.com",
            email="gate@example.com",
            password="pw",
        )
        # Default: ensure the user has a fresh free trial (5 min, untouched).
        FreeTrialUsage.objects.filter(user=self.user).delete()
        UserSubscription.objects.filter(user=self.user).delete()
        # Trigger trial creation via the signal that fires on user save:
        # the test_free_trial suite confirms this contract, but be
        # defensive in case the signal wasn't wired in test settings.
        FreeTrialUsage.objects.get_or_create(
            user=self.user, defaults={"free_seconds_granted": 5 * 60},
        )
        self.client.force_login(self.user)

    # ----- 1 -----
    def test_free_trial_student_can_open_voice_call_quick_page(self):
        """A brand-new student with 5 free minutes must reach the quick
        entry point (it will then redirect to the conversation page)."""
        r = self.client.get(reverse("tutor_voice_call_quick"))
        # Quick page is a redirect-on-success; if the gate rejected the
        # user we'd land on /subscribe/ instead.
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("/payments", r["Location"])  # url name "subscribe" → /payments/

    # ----- 2 -----
    def test_free_trial_student_redirects_to_conversation_voice_page(self):
        """The quick redirect must land on ``tutor_voice_call`` with the
        conversation pk that the helper created or reused."""
        r = self.client.get(reverse("tutor_voice_call_quick"))
        self.assertEqual(r.status_code, 302)
        # A conversation should now exist for this user.
        conv = TutorConversation.objects.filter(user=self.user).first()
        self.assertIsNotNone(conv)
        expected = reverse("tutor_voice_call", args=[conv.pk])
        self.assertEqual(r["Location"], expected)

    # ----- 3 -----
    def test_consumed_free_trial_student_cannot_open_voice_call_page(self):
        """Free trial used up + no subscription → redirected to subscribe."""
        _exhaust_free_trial(self.user)
        # Make sure no active subscription exists.
        UserSubscription.objects.filter(user=self.user).delete()
        self.user.profile.subscription_status = "inactive"
        self.user.profile.save()
        conv = TutorConversation.objects.create(user=self.user)
        r = self.client.get(reverse("tutor_voice_call", args=[conv.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/payments", r["Location"])  # url name "subscribe" → /payments/
        # And the quick page also bounces.
        r_quick = self.client.get(reverse("tutor_voice_call_quick"))
        self.assertEqual(r_quick.status_code, 302)
        self.assertIn("/payments", r_quick["Location"])

    # ----- 4 -----
    def test_subscribed_student_can_open_voice_call_page(self):
        """A paid student passes the gate regardless of trial state."""
        _exhaust_free_trial(self.user)
        _grant_subscription(self.user)
        conv = TutorConversation.objects.create(user=self.user)
        r = self.client.get(reverse("tutor_voice_call", args=[conv.pk]))
        self.assertEqual(r.status_code, 200)

    # ----- 5 -----
    def test_placement_voice_call_bypasses_subscription_gate_only_for_valid_attempt(self):
        """A real placement attempt — owned by the user and pointing at
        the same conversation — passes even with NO subscription and NO
        trial seconds."""
        from placement.models import PlacementAttempt
        _exhaust_free_trial(self.user)
        UserSubscription.objects.filter(user=self.user).delete()
        self.user.profile.subscription_status = "inactive"
        self.user.profile.save()
        conv = TutorConversation.objects.create(user=self.user)
        attempt = PlacementAttempt.objects.create(
            user=self.user,
            voice_conversation_id=conv.pk,
        )
        url = reverse("tutor_voice_call", args=[conv.pk]) + f"?placement_attempt={attempt.pk}"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    # ----- 6 -----
    def test_invalid_placement_attempt_does_not_bypass_paywall(self):
        """``?placement_attempt=<n>`` must NOT bypass the gate when the
        attempt is missing, belongs to someone else, or points at a
        different conversation."""
        from placement.models import PlacementAttempt
        _exhaust_free_trial(self.user)
        UserSubscription.objects.filter(user=self.user).delete()
        self.user.profile.subscription_status = "inactive"
        self.user.profile.save()
        conv = TutorConversation.objects.create(user=self.user)

        # (a) Attempt belongs to a DIFFERENT user.
        other = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="pw",
        )
        their_attempt = PlacementAttempt.objects.create(
            user=other, voice_conversation_id=conv.pk,
        )
        url = reverse("tutor_voice_call", args=[conv.pk]) + f"?placement_attempt={their_attempt.pk}"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/payments", r["Location"])  # url name "subscribe" → /payments/

        # (b) Attempt belongs to this user but points at a DIFFERENT conversation.
        other_conv = TutorConversation.objects.create(user=self.user)
        my_attempt_elsewhere = PlacementAttempt.objects.create(
            user=self.user, voice_conversation_id=other_conv.pk,
        )
        url = reverse("tutor_voice_call", args=[conv.pk]) + f"?placement_attempt={my_attempt_elsewhere.pk}"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/payments", r["Location"])  # url name "subscribe" → /payments/

        # (c) Garbage placement_attempt id.
        url = reverse("tutor_voice_call", args=[conv.pk]) + "?placement_attempt=9999999"
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/payments", r["Location"])  # url name "subscribe" → /payments/
