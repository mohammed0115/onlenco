"""Performance + timeout-safety tests for the tutor SPA endpoints.

Pins the contract that:
- AI/STT/TTS timeouts return friendly JSON, never bubble exceptions.
- Conversation history is capped (no full-history blowup).
- Per-step timing logs land on the `tutor.perf` channel so SREs can
  build dashboards without reverse-engineering log lines.
- TTS slowness does not block text delivery.
"""
from __future__ import annotations

import json
import logging
from unittest.mock import patch

import requests as real_requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from tutor.models import TutorConversation, TutorMessage

User = get_user_model()


class _LogCapture:
    """Tiny logging.Handler-as-list helper."""
    def __init__(self):
        self.records = []
    def attach(self, logger_name):
        self._logger = logging.getLogger(logger_name)
        self._handler = logging.Handler()
        self._handler.emit = self.records.append
        self._logger.addHandler(self._handler)
        self._logger.setLevel(logging.INFO)
    def detach(self):
        self._logger.removeHandler(self._handler)
    def messages(self):
        return [r.getMessage() for r in self.records]


@override_settings(AXES_ENABLED=False)
class TimeoutFallbackTests(TestCase):
    """When upstream AI calls time out, the API still returns JSON with
    a friendly error — never a 500 / exception page."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="t@perf.x", email="t@perf.x", password="pw",
        )
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.client.login(username="t@perf.x", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user)

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_chat_send_returns_friendly_text_when_ai_times_out(self):
        from tutor.services import _chat as chat_mod
        with patch.object(
            chat_mod.requests, "post",
            side_effect=real_requests.Timeout("upstream timed out"),
        ):
            r = self.client.post(
                reverse("api_tutor_chat_send"),
                json.dumps({"message": "hi", "conversation_id": self.conv.id}),
                content_type="application/json",
            )
        # Same contract as /chat/send/'s normal path — JSON, 200, with a
        # graceful fallback string in `content`. The user sees a friendly
        # bubble (no 500 page, no "Quick fix:" technical token).
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"].split(";")[0], "application/json")
        body = r.json()
        self.assertTrue(body["success"])
        content = body["ai_message"]["content"]
        self.assertTrue(content, "fallback must produce text")
        self.assertNotIn("Quick fix:", content,
                         "timeout fallback must not leak the 'Quick fix:' label")
        # Gentle ask-again wording (the new fallback).
        self.assertIn("again", content.lower())

    def test_voice_transcribe_returns_503_json_on_stt_failure(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile("rec.webm", b"x" * 2048, content_type="audio/webm")
        with patch(
            "placement.services.stt.transcribe",
            side_effect=real_requests.Timeout("stt down"),
        ):
            r = self.client.post(
                reverse("api_tutor_voice_transcribe"),
                {"audio": f},
            )
        self.assertEqual(r.status_code, 503)
        body = r.json()
        self.assertFalse(body["success"])
        self.assertEqual(body["error"], "stt_unavailable")
        self.assertIn("message", body)

    def test_voice_tts_returns_503_json_on_tts_failure(self):
        with patch(
            "tutor.services.tts.synthesize",
            side_effect=real_requests.Timeout("tts down"),
        ):
            r = self.client.post(
                reverse("api_tutor_voice_tts"),
                json.dumps({"text": "hello", "language": "en"}),
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 503)
        self.assertFalse(r.json()["success"])


@override_settings(AXES_ENABLED=False, AI_API_KEY="")
class HistoryCapTests(TestCase):
    """Even with 30 stored messages, the LLM payload only carries the
    last `MAX_HISTORY_MESSAGES`."""

    def setUp(self):
        self.user = User.objects.create_user(username="h@perf.x", password="pw")
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.conv = TutorConversation.objects.create(user=self.user)
        for i in range(30):
            TutorMessage.objects.create(
                conversation=self.conv,
                role="user" if i % 2 == 0 else "assistant",
                content=f"msg-{i}",
            )

    def test_payload_only_includes_last_10_history_messages(self):
        from tutor.services._chat import _build_payload, MAX_HISTORY_MESSAGES
        self.assertEqual(MAX_HISTORY_MESSAGES, 10)
        payload = _build_payload(self.conv, "what now?", voice=False, stream=False)
        # messages = [system, …history…, current_user]
        history = payload["messages"][1:-1]
        self.assertLessEqual(len(history), MAX_HISTORY_MESSAGES)


class PerfLoggingTests(TestCase):
    """`tutor.perf` channel emits step duration lines."""

    def setUp(self):
        self.cap = _LogCapture()
        self.cap.attach("tutor.perf")
        self.user = User.objects.create_user(username="p@perf.x", password="pw")
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.client.login(username="p@perf.x", password="pw")

    def tearDown(self):
        self.cap.detach()

    @override_settings(AXES_ENABLED=False, AI_API_KEY="")
    def test_chat_stream_emits_first_token_log(self):
        conv = TutorConversation.objects.create(user=self.user)
        r = self.client.post(
            reverse("api_tutor_chat_stream"),
            json.dumps({"message": "hi", "conversation_id": conv.id}),
            content_type="application/json",
        )
        list(r.streaming_content)  # drain so the generator runs
        msgs = "\n".join(self.cap.messages())
        self.assertIn("step=chat_first_token", msgs)
        self.assertIn("step=chat_stream_total", msgs)
        self.assertIn("step=stream_view_total", msgs)


@override_settings(AXES_ENABLED=False, AI_API_KEY="")
class TtsDoesNotBlockTextTests(TestCase):
    """The text reply lands in `chat_send`'s JSON regardless of TTS health.

    The SPA's audio path is downstream + opt-in, so this test simply
    verifies the chat endpoint *never* calls TTS itself. Server-side
    TTS only fires when the client posts to `/voice/tts/` separately."""

    def setUp(self):
        self.user = User.objects.create_user(username="ttx@perf.x", password="pw")
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.client.login(username="ttx@perf.x", password="pw")

    def test_chat_send_does_not_call_tts(self):
        with patch("tutor.services.tts.synthesize") as mock_tts:
            r = self.client.post(
                reverse("api_tutor_chat_send"),
                json.dumps({"message": "hi"}),
                content_type="application/json",
            )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["success"])
        mock_tts.assert_not_called()
