"""Coverage for the live voice-call (OpenAI Realtime) feature.

We don't actually open a WebRTC peer in tests — we just pin the contract
of the Django-side endpoints:

- The voice-call page renders with the SPA hooks the JS needs.
- The session endpoint returns 401 for anonymous, 402 for unsubscribed,
  429 when the daily cap is exhausted, and a JSON token payload on
  success (with the upstream OpenAI call mocked so no API key is hit).
- The log endpoint records minutes + persists the spoken turns as
  TutorMessage rows.
"""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tutor.models import TutorConversation, TutorMessage

User = get_user_model()


def _activate_subscription(user):
    prof = user.profile
    prof.subscription_status = "active"
    prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
    prof.save()


@override_settings(AXES_ENABLED=False)
class VoiceCallPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vc@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="vc@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user)

    def test_page_loads_with_call_hooks(self):
        r = self.client.get(reverse("tutor_voice_call", args=[self.conv.pk]))
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        for hook in ['id="callOrb"', 'id="startCallBtn"', 'id="endCallBtn"', 'onlencoCall']:
            self.assertIn(hook, body, f"missing call hook: {hook}")

    def test_anonymous_redirected(self):
        self.client.logout()
        r = self.client.get(reverse("tutor_voice_call", args=[self.conv.pk]))
        self.assertEqual(r.status_code, 302)


@override_settings(AXES_ENABLED=False)
class VoiceCallSessionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="vcs@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="vcs@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user)
        self.url = reverse("api_tutor_voice_call_session")

    def test_anonymous_returns_401(self):
        self.client.logout()
        r = self.client.post(self.url, {}, content_type="application/json")
        self.assertIn(r.status_code, (401, 403))

    def test_unsubscribed_with_consumed_trial_returns_402(self):
        # Sprint 2 spec: unsubscribed users get the one-shot 5-minute
        # trial first; only once that is drained do they get 402.
        from subscriptions.services.quota_service import consume_free_trial_seconds
        self.user.profile.subscription_status = "inactive"
        self.user.profile.save()
        consume_free_trial_seconds(self.user, 5 * 60)  # drain trial
        r = self.client.post(self.url, {}, content_type="application/json")
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()["error"], "limit_reached")

    def test_returns_ephemeral_token_on_success(self):
        fake_session = {
            "id": "sess_abc",
            "client_secret": {"value": "ek_test_123"},
            "expires_at": 9999999999,
        }
        with patch(
            "tutor.services.realtime_session.request_ephemeral_session",
            return_value=fake_session,
        ) as mock_req:
            r = self.client.post(
                self.url,
                {"conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["client_secret"], "ek_test_123")
        self.assertEqual(body["session_id"], "sess_abc")
        # System prompt is built once and forwarded to the upstream.
        kwargs = mock_req.call_args.kwargs
        self.assertIn("system_prompt", kwargs)
        self.assertIn("Layla", kwargs["system_prompt"])

    def test_tutor_first_contract(self):
        """The browser must be told to make the TUTOR open the call (the
        student never starts). The JS uses auto_start + opening_instruction to
        send the opening response.create."""
        fake_session = {
            "id": "sess_abc", "client_secret": {"value": "ek_test_123"},
            "expires_at": 9999999999,
        }
        with patch(
            "tutor.services.realtime_session.request_ephemeral_session",
            return_value=fake_session,
        ):
            r = self.client.post(
                self.url, {"conversation_id": self.conv.id},
                content_type="application/json",
            )
        body = r.json()
        self.assertTrue(body["auto_start"])                       # tutor speaks first
        self.assertIn("opening_instruction", body)
        self.assertIn("Do not wait for the student", body["opening_instruction"])

    def test_daily_cap_blocks_further_sessions(self):
        # Sprint 2: cap is DB-backed (subscription daily quota OR trial).
        # Drain BOTH buckets and verify the endpoint refuses with 402.
        from subscriptions.services.quota_service import (
            consume_ai_tutor_seconds, consume_free_trial_seconds,
            daily_ai_tutor_limit_seconds,
        )
        # Drain subscription (if any) and trial.
        consume_ai_tutor_seconds(self.user, max(daily_ai_tutor_limit_seconds(self.user), 0))
        consume_free_trial_seconds(self.user, 5 * 60)
        r = self.client.post(self.url, {}, content_type="application/json")
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()["error"], "limit_reached")


@override_settings(AXES_ENABLED=False)
class VoiceCallLogTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="vcl@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="vcl@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user)
        self.url = reverse("api_tutor_voice_call_log")

    def test_logs_seconds_and_persists_turns(self):
        r = self.client.post(self.url, {
            "conversation_id": self.conv.id,
            "seconds": 42,
            "transcript": [
                {"role": "user", "content": "Hello Layla"},
                {"role": "assistant", "content": "Hey! How was your day?"},
            ],
        }, content_type="application/json")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["logged_seconds"], 42)
        self.assertEqual(self.conv.messages.count(), 2)
        msgs = list(self.conv.messages.all())
        self.assertEqual(msgs[0].role, "user")
        self.assertEqual(msgs[0].content, "Hello Layla")
        self.assertEqual(msgs[1].role, "assistant")

    def test_advances_daily_counter(self):
        # Sprint 2: counter lives on FreeTrialUsage (no subscription set up here)
        # or UserDailyQuota (if subscribed). With the legacy ``_activate_subscription``
        # helper we only flip the profile flag — no UserSubscription row exists,
        # so the deduction lands on the free trial bucket.
        from subscriptions.models import FreeTrialUsage
        self.client.post(self.url, {"seconds": 60}, content_type="application/json")
        trial = FreeTrialUsage.objects.get(user=self.user)
        self.assertEqual(trial.free_seconds_used, 60)

    def test_blocks_other_users_conversation(self):
        other = User.objects.create_user(username="other-vcl@x.com", password="pw")
        other_conv = TutorConversation.objects.create(user=other)
        r = self.client.post(self.url, {
            "conversation_id": other_conv.id,
            "seconds": 5,
        }, content_type="application/json")
        self.assertEqual(r.status_code, 403)


@override_settings(AXES_ENABLED=False)
class CallResponseConsistencyTests(TestCase):
    """Prompt 17.4 D/E/H — unified call start/end responses + backend protection.

    The no-plan active user falls back to the one-shot 5-minute trial, so the
    daily allowance here is 300 seconds.
    """

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="ccs@x.com", password="pw")
        _activate_subscription(self.user)
        self.client.login(username="ccs@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user)
        self.start_url = reverse("api_tutor_voice_call_session")
        self.log_url = reverse("api_tutor_voice_call_log")
        self._fake = {"id": "sess_x", "client_secret": {"value": "ek_x"},
                      "expires_at": 9999999999}

    def _start(self):
        with patch("tutor.services.realtime_session.request_ephemeral_session",
                   return_value=self._fake):
            return self.client.post(
                self.start_url, {"conversation_id": self.conv.id},
                content_type="application/json",
            )

    def _open_call(self):
        from tutor.services import usage_limits as ul
        return ul.start_ai_tutor_usage(self.user, ul.MODE_REGULAR_AI_TUTOR_CALL).session_id

    # H1
    def test_start_returns_remaining_and_daily_limit(self):
        body = self._start().json()
        self.assertIn("remaining_seconds", body)
        self.assertEqual(body["daily_limit_seconds"], 300)
        self.assertIn("max_session_seconds", body)
        self.assertEqual(body["status"], "ok")

    # H2
    def test_start_blocked_with_daily_limit_reached(self):
        from subscriptions.services.quota_service import consume_free_trial_seconds
        consume_free_trial_seconds(self.user, 300)
        r = self.client.post(self.start_url, {"conversation_id": self.conv.id},
                             content_type="application/json")
        self.assertEqual(r.status_code, 402)
        body = r.json()
        self.assertEqual(body["error_code"], "DAILY_LIMIT_REACHED")
        self.assertIn("اليومي", body["message_ar"])
        self.assertEqual(body["remaining_seconds"], 0)

    # H8
    def test_start_provider_failure_returns_error_code(self):
        with patch("tutor.services.realtime_session.request_ephemeral_session",
                   side_effect=RuntimeError("boom")):
            r = self.client.post(self.start_url, {"conversation_id": self.conv.id},
                                 content_type="application/json")
        self.assertEqual(r.status_code, 503)
        body = r.json()
        self.assertEqual(body["error_code"], "CALL_PROVIDER_UNAVAILABLE")
        self.assertIn("المكالمة", body["message_ar"])

    # H3
    def test_end_returns_used_and_remaining(self):
        sid = self._open_call()
        body = self.client.post(
            self.log_url,
            {"conversation_id": self.conv.id, "seconds": 60, "tutor_session_id": sid},
            content_type="application/json",
        ).json()
        self.assertEqual(body["used_seconds"], 60)
        self.assertEqual(body["remaining_seconds"], 240)
        self.assertEqual(body["daily_limit_seconds"], 300)
        self.assertEqual(body["status"], "ended")

    # H4
    def test_end_killed_by_quota_is_safe(self):
        from tutor.services import usage_limits as ul
        sid = self._open_call()
        body = self.client.post(
            self.log_url,
            {"conversation_id": self.conv.id, "seconds": 50,
             "tutor_session_id": sid, "killed_by_quota": True},
            content_type="application/json",
        ).json()
        self.assertTrue(body["killed_by_quota"])
        self.assertEqual(ul.get_daily_used_seconds(self.user), 50)

    # H5
    def test_end_twice_does_not_double_charge(self):
        from tutor.services import usage_limits as ul
        sid = self._open_call()
        for _ in range(2):
            self.client.post(
                self.log_url,
                {"conversation_id": self.conv.id, "seconds": 60, "tutor_session_id": sid},
                content_type="application/json",
            )
        self.assertEqual(ul.get_daily_used_seconds(self.user), 60)

    # H6
    def test_negative_client_duration_is_clamped(self):
        from tutor.services import usage_limits as ul
        sid = self._open_call()
        body = self.client.post(
            self.log_url,
            {"conversation_id": self.conv.id, "seconds": -50, "tutor_session_id": sid},
            content_type="application/json",
        ).json()
        self.assertEqual(body["used_seconds"], 0)
        self.assertEqual(ul.get_daily_used_seconds(self.user), 0)

    def test_huge_client_duration_cannot_exceed_daily_allowance(self):
        from tutor.services import usage_limits as ul
        sid = self._open_call()
        self.client.post(
            self.log_url,
            {"conversation_id": self.conv.id, "seconds": 999999999, "tutor_session_id": sid},
            content_type="application/json",
        )
        self.assertLessEqual(ul.get_daily_used_seconds(self.user), 300)
