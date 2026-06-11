"""Prompt 17.2B — chat_send and voice_call_log routed through the usage facade.

These pin the contract that ``tutor.services.usage_limits`` is the ONLY usage
entry point: text chat no longer consults ``core.services.ai_usage``, voice
calls finalise through the facade, and placement still never consumes.
"""
from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import SubscriptionPlan, UserDailyQuota, UserSubscription
from tutor.models import TutorConversation
from tutor.services import usage_limits as ul

User = get_user_model()


def _subscribe(user, minutes):
    now = timezone.now()
    plan = SubscriptionPlan.objects.create(
        code=f"plan-{user.username}", name_en="P", name_ar="خطة", price_sdg=0,
        ai_tutor_daily_minutes=minutes, library_audio_daily_minutes=0,
    )
    UserSubscription.objects.create(
        user=user, plan=plan, status="active",
        start_date=now - timedelta(days=1), end_date=now + timedelta(days=29),
    )
    prof = user.profile
    prof.subscription_status = "active"
    prof.subscription_expires_at = now + timedelta(days=29)
    prof.save()


@override_settings(AXES_ENABLED=False)
class ChatSendFacadeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="cs@x.com", password="pw")
        _subscribe(self.user, 5)
        self.conv = TutorConversation.objects.create(user=self.user)
        self.client.login(username="cs@x.com", password="pw")
        self.url = reverse("api_tutor_chat_send")

    def test_text_chat_does_not_call_core_is_within_limit(self):
        # The old parallel source must never be consulted from the tutor path.
        with patch("core.services.ai_usage.is_within_limit") as old_gate, \
             patch("tutor.api.views.chat", return_value="ok"):
            r = self.client.post(
                self.url, {"message": "hi", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        old_gate.assert_not_called()

    def test_text_chat_does_not_consume_voice_seconds_by_default(self):
        with patch("tutor.api.views.chat", return_value="ok"):
            self.client.post(
                self.url,
                {"message": "hi", "conversation_id": self.conv.id, "speaking_seconds": 40},
                content_type="application/json",
            )
        self.assertEqual(ul.get_daily_used_seconds(self.user), 0)

    @override_settings(TUTOR_TEXT_MESSAGE_CONSUMES_MINUTES=True)
    def test_text_chat_consumes_when_configured(self):
        with patch("tutor.api.views.chat", return_value="ok"):
            self.client.post(
                self.url,
                {"message": "hi", "conversation_id": self.conv.id, "speaking_seconds": 25},
                content_type="application/json",
            )
        self.assertEqual(ul.get_daily_used_seconds(self.user), 25)

    @override_settings(TUTOR_TEXT_MESSAGE_CONSUMES_MINUTES=True)
    def test_text_chat_blocked_when_configured_and_exhausted(self):
        ul.deduct_usage_seconds(self.user, 300)  # exhaust the 5-min plan
        with patch("tutor.api.views.chat", return_value="ok") as mock_chat:
            r = self.client.post(
                self.url, {"message": "hi", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 402)
        mock_chat.assert_not_called()


@override_settings(AXES_ENABLED=False)
class VoiceCallLogFacadeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="cl@x.com", password="pw")
        _subscribe(self.user, 5)
        self.conv = TutorConversation.objects.create(user=self.user)
        self.client.login(username="cl@x.com", password="pw")
        self.url = reverse("api_tutor_voice_call_log")

    def _start_call(self):
        usage = ul.start_ai_tutor_usage(self.user, ul.MODE_REGULAR_AI_TUTOR_CALL)
        return usage.session_id

    def test_call_finalize_deducts_through_facade(self):
        sid = self._start_call()
        r = self.client.post(
            self.url,
            {"seconds": 75, "tutor_session_id": sid, "conversation_id": self.conv.id},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ul.get_daily_used_seconds(self.user), 75)

    def test_call_finalize_is_not_double_charged(self):
        sid = self._start_call()
        for _ in range(2):  # duplicate hang-up logs
            self.client.post(
                self.url,
                {"seconds": 75, "tutor_session_id": sid, "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(ul.get_daily_used_seconds(self.user), 75)

    def test_start_and_finish_remaining_is_consistent(self):
        allowed = ul.get_daily_allowed_seconds(self.user)
        sid = self._start_call()
        self.client.post(
            self.url,
            {"seconds": 90, "tutor_session_id": sid, "conversation_id": self.conv.id},
            content_type="application/json",
        )
        self.assertEqual(ul.get_remaining_seconds(self.user), allowed - 90)


@override_settings(AXES_ENABLED=False)
class PlacementStillFreeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="pl@x.com", password="pw")
        _subscribe(self.user, 5)
        self.conv = TutorConversation.objects.create(user=self.user)
        self.client.login(username="pl@x.com", password="pw")
        self.url = reverse("api_tutor_voice_call_log")

    def test_placement_call_log_does_not_consume_minutes(self):
        from placement.models import PlacementAttempt
        attempt = PlacementAttempt.objects.create(
            user=self.user, voice_conversation_id=self.conv.pk,
        )
        # Open a placement session via the facade (skip_quota, placement_voice).
        usage = ul.start_ai_tutor_usage(self.user, ul.MODE_PLACEMENT_SPEAKING_CALL)
        r = self.client.post(
            self.url,
            {"seconds": 120, "tutor_session_id": usage.session_id,
             "conversation_id": self.conv.id},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        # Placement must NOT touch the daily AI-Tutor seconds.
        self.assertEqual(ul.get_daily_used_seconds(self.user), 0)
        quota = UserDailyQuota.objects.filter(user=self.user, date=timezone.localdate()).first()
        self.assertTrue(quota is None or quota.ai_tutor_seconds_used == 0)
        self.assertTrue(attempt.pk)  # attempt row exists (placement data only)
