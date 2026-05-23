"""Safety contracts when the OpenAI / AI_API_KEY is missing.

The Tutor + TTS layer must degrade gracefully when keys are not
configured (dev machines, mis-configured staging) — never crash, never
deduct paid minutes for a session that could not start.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings


User = get_user_model()


class AIKeySafetyTests(TestCase):
    """Three contracts the MVP relies on when keys are missing."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="keysafe@example.com",
            email="keysafe@example.com",
            password="pw",
        )

    @override_settings(AI_API_KEY="")
    def test_realtime_session_missing_api_key_does_not_crash(self):
        """``request_ephemeral_session`` must return ``None`` (not raise)
        when no API key is configured."""
        from tutor.services.realtime_session import request_ephemeral_session
        result = request_ephemeral_session(system_prompt="hi", voice="alloy")
        self.assertIsNone(result)

    @override_settings(AI_API_KEY="")
    def test_missing_api_key_does_not_deduct_minutes(self):
        """When AI is unconfigured, hitting the voice-call endpoint must
        leave the user's daily quota counters untouched."""
        from subscriptions.services import quota_service
        # Seed an active subscription so the quota check passes the gate
        # and we actually reach the realtime call (where the key is missing).
        from subscriptions.models import SubscriptionPlan
        from subscriptions.services import subscription_service
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(
            user=self.user, plan=plan, duration_days=30,
        )
        quota_before = quota_service.get_or_create_today_quota(self.user)
        seconds_before = quota_before.ai_tutor_seconds_used

        self.client.force_login(self.user)
        resp = self.client.post("/api/v1/tutor/voice/", data={}, content_type="application/json")

        # The endpoint returns an error (503 ai_unavailable), never 2xx.
        self.assertIn(resp.status_code, (status_codes := {402, 503}))
        # And the daily quota row is unchanged.
        quota_after = quota_service.get_or_create_today_quota(self.user)
        self.assertEqual(quota_after.ai_tutor_seconds_used, seconds_before)

    @override_settings(AI_API_KEY="")
    def test_tts_failure_does_not_deduct_library_audio_quota(self):
        """When TTS returns empty (no key), the library quota counter
        must stay at zero usage — the browser plays no audio so no
        seconds are reported to ``end_session``."""
        from subscriptions.services import quota_service, library_audio_service
        from subscriptions.models import SubscriptionPlan
        from subscriptions.services import subscription_service

        # Seed a paid plan so library_audio_daily_minutes > 0.
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        subscription_service.activate_subscription(
            user=self.user, plan=plan, duration_days=30,
        )
        quota = quota_service.get_or_create_today_quota(self.user)
        seconds_used_before = quota.library_seconds_used

        # 1. Synthesizing a chunk with no key returns empty audio,
        #    not an exception.
        audio = library_audio_service.synthesize_chunk("Hello world", voice="alloy", language="en")
        self.assertEqual(audio.get("audio_b64", ""), "")

        # 2. The browser, seeing no audio, would never report playback
        #    seconds — simulate by ending a session with 0 seconds.
        session = library_audio_service.start_session(
            self.user, chapter_id=1, chapter_title="Demo",
        )
        library_audio_service.end_session(
            session.pk, actual_seconds=0, killed_by_quota=False,
        )

        # The library quota counter is unchanged.
        quota.refresh_from_db()
        self.assertEqual(quota.library_seconds_used, seconds_used_before)
