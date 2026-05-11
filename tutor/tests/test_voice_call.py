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

    def test_unsubscribed_returns_402(self):
        self.user.profile.subscription_status = "inactive"
        self.user.profile.save()
        r = self.client.post(self.url, {}, content_type="application/json")
        self.assertEqual(r.status_code, 402)

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

    def test_daily_cap_blocks_further_sessions(self):
        # Hit the cap directly via the cache key the service uses.
        from tutor.services.realtime_session import _cap_cache_key
        cache.set(_cap_cache_key(self.user.id), 31 * 60, timeout=60)  # 31 min ≥ default 30
        r = self.client.post(self.url, {}, content_type="application/json")
        self.assertEqual(r.status_code, 429)
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
        from tutor.services.realtime_session import _cap_cache_key
        self.client.post(self.url, {"seconds": 60}, content_type="application/json")
        used = cache.get(_cap_cache_key(self.user.id), 0) or 0
        self.assertEqual(used, 60)

    def test_blocks_other_users_conversation(self):
        other = User.objects.create_user(username="other-vcl@x.com", password="pw")
        other_conv = TutorConversation.objects.create(user=other)
        r = self.client.post(self.url, {
            "conversation_id": other_conv.id,
            "seconds": 5,
        }, content_type="application/json")
        self.assertEqual(r.status_code, 403)
