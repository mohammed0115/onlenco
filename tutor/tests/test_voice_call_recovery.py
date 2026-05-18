"""Concurrent-session recovery + lip-sync provider interface tests."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from subscriptions.models import AITutorSession
from subscriptions.services import session_service
from tutor.services.lip_sync import (
    CssOnlyProvider,
    DIDProvider,
    HeyGenProvider,
    describe_capabilities,
    get_provider,
)


User = get_user_model()


@override_settings(AXES_ENABLED=False)
class CancelStaleEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="stale@x.com", password="pw")
        self.client.login(username="stale@x.com", password="pw")

    def test_cancel_stale_with_no_open_session(self):
        response = self.client.post(reverse("api_tutor_voice_call_cancel_stale"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["cancelled"])

    def test_cancel_stale_closes_open_session(self):
        AITutorSession.objects.create(
            user=self.user, source="voice_call", status="in_progress",
            quota_source="free_trial",
        )
        response = self.client.post(reverse("api_tutor_voice_call_cancel_stale"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["cancelled"])
        sess = AITutorSession.objects.get(user=self.user)
        self.assertEqual(sess.status, "cancelled")

    def test_anonymous_blocked(self):
        self.client.logout()
        response = self.client.post(reverse("api_tutor_voice_call_cancel_stale"))
        self.assertIn(response.status_code, (401, 403))


class StaleAutoCleanupTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="auto@x.com", password="pw")

    def test_stale_session_auto_cancelled_on_start(self):
        # Create an "old" in_progress session (>10 min) — pretend the browser crashed.
        old = AITutorSession.objects.create(
            user=self.user, source="voice_call", status="in_progress",
            quota_source="free_trial",
        )
        AITutorSession.objects.filter(pk=old.pk).update(
            started_at=timezone.now() - timedelta(minutes=15),
        )
        # Without auto-cleanup, starting a new session would raise
        # ConcurrentSessionExists. With cleanup, it should succeed.
        new = session_service.start_session(self.user)
        self.assertEqual(new.status, "in_progress")
        old.refresh_from_db()
        self.assertEqual(old.status, "cancelled")

    def test_recent_open_session_also_cancelled_on_new_start(self):
        # Updated policy: even a 5-minute-old in_progress row gets
        # cancelled when the user clicks Start again. We treat the new
        # click as "kill the old one, give me a fresh call".
        recent = AITutorSession.objects.create(
            user=self.user, source="voice_call", status="in_progress",
            quota_source="free_trial",
        )
        AITutorSession.objects.filter(pk=recent.pk).update(
            started_at=timezone.now() - timedelta(minutes=5),
        )
        new = session_service.start_session(self.user)
        self.assertEqual(new.status, "in_progress")
        recent.refresh_from_db()
        self.assertEqual(recent.status, "cancelled")


class LipSyncProviderTests(TestCase):
    def test_default_provider_is_css_only(self):
        provider = get_provider()
        self.assertEqual(provider.name, "css_only")
        self.assertTrue(provider.is_available())

    def test_css_only_returns_local_session(self):
        provider = CssOnlyProvider()
        session = provider.create_stream_session(
            avatar_image_url="https://example.com/face.jpg",
            voice="alloy", language="en",
        )
        self.assertEqual(session["provider"], "css_only")
        self.assertTrue(session["supported"])

    def test_did_provider_unavailable_without_key(self):
        with override_settings(DID_API_KEY=""):
            self.assertFalse(DIDProvider().is_available())

    def test_heygen_provider_unavailable_without_key(self):
        with override_settings(HEYGEN_API_KEY=""):
            self.assertFalse(HeyGenProvider().is_available())

    def test_configured_unavailable_provider_falls_back_to_css(self):
        with override_settings(LIP_SYNC_PROVIDER="did", DID_API_KEY=""):
            provider = get_provider()
            self.assertEqual(provider.name, "css_only")

    def test_describe_capabilities_dict_shape(self):
        with override_settings(LIP_SYNC_PROVIDER="css_only"):
            caps = describe_capabilities()
            self.assertEqual(caps["active_provider"], "css_only")
            self.assertIn("css_only", caps["providers"])
            self.assertIn("did", caps["providers"])
            self.assertIn("heygen", caps["providers"])
