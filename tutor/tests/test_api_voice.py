"""Tests for the voice-pipeline endpoints (transcribe / respond / tts)."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from speech.models import SpeakingAttempt
from tutor.models import TutorConversation, TutorMessage

User = get_user_model()


def _audio_blob(name="recording.webm", size_bytes=2048):
    """Build a fake WebM upload — enough to satisfy size validation."""
    f = SimpleUploadedFile(name, b"x" * size_bytes, content_type="audio/webm")
    return f


@override_settings(AXES_ENABLED=False)
class VoiceTranscribeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="v@x.com", password="pw")
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.client.login(username="v@x.com", password="pw")
        self.url = reverse("api_tutor_voice_transcribe")

    def test_anonymous_returns_401(self):
        self.client.logout()
        r = self.client.post(self.url, {"audio": _audio_blob()})
        self.assertIn(r.status_code, (401, 403))

    def test_missing_audio_returns_400(self):
        r = self.client.post(self.url, {})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "no_audio")

    def test_oversized_audio_rejected(self):
        from speech.services.audio_validation import MAX_BYTES
        big = _audio_blob(size_bytes=MAX_BYTES + 1)
        r = self.client.post(self.url, {"audio": big})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "too_large")

    def test_bad_extension_rejected(self):
        f = SimpleUploadedFile("bad.exe", b"x" * 1024, content_type="audio/webm")
        r = self.client.post(self.url, {"audio": f})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "bad_extension")

    def test_success_saves_speaking_attempt(self):
        with patch(
            "placement.services.stt.transcribe",
            return_value={"transcript": "hello world", "duration_seconds": 3, "confidence": 0.9},
        ):
            r = self.client.post(self.url, {"audio": _audio_blob()})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["transcript"], "hello world")
        self.assertEqual(SpeakingAttempt.objects.filter(user=self.user).count(), 1)
        attempt = SpeakingAttempt.objects.get(user=self.user)
        self.assertEqual(attempt.source, "tutor")
        self.assertEqual(attempt.transcript, "hello world")

    def test_empty_transcript_returns_friendly_message(self):
        with patch(
            "placement.services.stt.transcribe",
            return_value={"transcript": "", "duration_seconds": 1, "confidence": 0.0},
        ):
            r = self.client.post(self.url, {"audio": _audio_blob()})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["transcript"], "")
        self.assertIn("message", body)


@override_settings(AXES_ENABLED=False)
class VoiceRespondTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="vr@x.com", password="pw")
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.conv = TutorConversation.objects.create(user=self.user)
        self.client.login(username="vr@x.com", password="pw")
        self.url = reverse("api_tutor_voice_respond")

    def test_anonymous_returns_401(self):
        self.client.logout()
        r = self.client.post(self.url, {"transcript": "hi"}, content_type="application/json")
        self.assertIn(r.status_code, (401, 403))

    def test_returns_humanized_speech_text(self):
        with patch("tutor.api.views.chat", return_value="Your weekly_assessment_available!"):
            r = self.client.post(
                self.url,
                {"transcript": "hi", "conversation_id": self.conv.id, "speaking_seconds": 5},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["success"])
        self.assertNotIn("weekly_assessment_available", body["ai_message"]["speech_text"])

    def test_voice_flag_passed_to_chat(self):
        with patch("tutor.api.views.chat", return_value="ok") as mock_chat:
            self.client.post(
                self.url,
                {"transcript": "hi", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        _, kwargs = mock_chat.call_args
        self.assertTrue(kwargs.get("voice"))

    def test_blocks_other_users_conversation(self):
        other = User.objects.create_user(username="other2@x.com", password="pw")
        other_conv = TutorConversation.objects.create(user=other)
        r = self.client.post(
            self.url,
            {"transcript": "hi", "conversation_id": other_conv.id},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 403)


@override_settings(AXES_ENABLED=False)
class VoiceTtsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tts@x.com", password="pw")
        self.client.login(username="tts@x.com", password="pw")
        self.url = reverse("api_tutor_voice_tts")

    def test_anonymous_returns_401(self):
        self.client.logout()
        r = self.client.post(self.url, {"text": "hi"}, content_type="application/json")
        self.assertIn(r.status_code, (401, 403))

    def test_humanizes_before_synthesizing(self):
        with patch("tutor.services.tts.synthesize", return_value={"audio_b64": "", "format": ""}):
            r = self.client.post(
                self.url,
                {"text": "weekly_assessment_available", "language": "en"},
                content_type="application/json",
            )
        body = r.json()
        self.assertTrue(body["success"])
        # Underscore name is humanised, never echoed raw.
        self.assertNotIn("_", body["speech_text"])

    def test_empty_text_returns_400(self):
        r = self.client.post(self.url, {"text": "  "}, content_type="application/json")
        self.assertEqual(r.status_code, 400)


@override_settings(AXES_ENABLED=False)
class VoiceMessageUsageGateTests(TestCase):
    """Prompt 17.2 — voice messages enforce + deduct daily AI-Tutor seconds."""

    def setUp(self):
        from datetime import timedelta
        from django.core.cache import cache
        from subscriptions.models import SubscriptionPlan, UserSubscription
        cache.clear()
        self.user = User.objects.create_user(username="vu@x.com", password="pw")
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timedelta(days=30)
        prof.save()
        now = timezone.now()
        self.plan = SubscriptionPlan.objects.create(
            code="vu-2m", name_en="P", name_ar="خطة", price_sdg=0,
            ai_tutor_daily_minutes=2, library_audio_daily_minutes=0,
        )
        UserSubscription.objects.create(
            user=self.user, plan=self.plan, status="active",
            start_date=now - timedelta(days=1), end_date=now + timedelta(days=29),
        )
        self.conv = TutorConversation.objects.create(user=self.user)
        self.client.login(username="vu@x.com", password="pw")
        self.url = reverse("api_tutor_voice_respond")

    def test_voice_message_deducts_seconds(self):
        from tutor.services import usage_limits as ul
        with patch("tutor.api.views.chat", return_value="ok"):
            r = self.client.post(
                self.url,
                {"transcript": "hi", "conversation_id": self.conv.id, "speaking_seconds": 45},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ul.get_daily_used_seconds(self.user), 45)

    def test_voice_message_blocked_when_limit_reached(self):
        from tutor.services import usage_limits as ul
        ul.deduct_voice_message_usage(self.user, 120)  # exhaust the 2-min plan
        with patch("tutor.api.views.chat", return_value="ok") as mock_chat:
            r = self.client.post(
                self.url,
                {"transcript": "hi", "conversation_id": self.conv.id, "speaking_seconds": 10},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 402)
        self.assertIn("اليومي", r.json().get("message", ""))
        # Backend cannot be bypassed: the AI was never even called.
        mock_chat.assert_not_called()

    # ---- Prompt 17.3 G: API response consistency ----------------------------
    def test_success_returns_usage_snapshot(self):
        with patch("tutor.api.views.chat", return_value="ok"):
            r = self.client.post(
                self.url,
                {"transcript": "hi", "conversation_id": self.conv.id, "speaking_seconds": 45},
                content_type="application/json",
            )
        body = r.json()
        self.assertEqual(body["used_seconds"], 45)
        self.assertEqual(body["remaining_seconds"], 75)
        self.assertEqual(body["daily_limit_seconds"], 120)

    def test_blocked_returns_error_code_and_arabic(self):
        from tutor.services import usage_limits as ul
        ul.deduct_usage_seconds(self.user, 120)  # exhaust 2-min plan
        with patch("tutor.api.views.chat", return_value="ok"):
            r = self.client.post(
                self.url, {"transcript": "hi", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 402)
        body = r.json()
        self.assertEqual(body["error_code"], "DAILY_LIMIT_REACHED")
        self.assertIn("اليومي", body["message_ar"])
        self.assertEqual(body["remaining_seconds"], 0)

    def test_empty_transcript_returns_friendly_arabic(self):
        with patch("tutor.api.views.chat", return_value="ok"):
            r = self.client.post(
                self.url, {"transcript": "   ", "conversation_id": self.conv.id},
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertEqual(body["error_code"], "MICROPHONE_TOO_SHORT")
        self.assertIn("قصير", body["message_ar"])

    def test_idempotency_key_prevents_double_deduct(self):
        from tutor.services import usage_limits as ul
        with patch("tutor.api.views.chat", return_value="ok"):
            for _ in range(2):
                self.client.post(
                    self.url,
                    {"transcript": "hi", "conversation_id": self.conv.id,
                     "speaking_seconds": 30, "idempotency_key": "dup-1"},
                    content_type="application/json",
                )
        self.assertEqual(ul.get_daily_used_seconds(self.user), 30)
