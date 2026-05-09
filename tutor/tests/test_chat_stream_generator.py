"""Unit tests for `tutor.services.chat_stream_tokens` — the generator that
yields token deltas from the upstream OpenAI-compatible stream."""
from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from tutor.models import TutorConversation
from tutor.services import chat_stream_tokens

User = get_user_model()


class _StreamingResponseStub:
    """Mimics requests.Response for `iter_lines` streaming."""
    status_code = 200

    def __init__(self, lines):
        self._lines = lines

    def raise_for_status(self):
        pass

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            yield line


class ChatStreamTokensTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="g@x.com", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user, topic="grammar")

    @override_settings(AI_API_KEY="")
    def test_no_api_key_yields_stub_reply(self):
        out = list(chat_stream_tokens(self.conv, "I goes home"))
        self.assertEqual(len(out), 1)
        self.assertIn("stub", out[0])

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_yields_each_delta_in_order(self):
        # OpenAI-compatible SSE shape: each `data: {...}` line has a
        # `choices[0].delta.content` containing one token chunk.
        lines = [
            'data: {"choices":[{"delta":{"content":"Hi"}}]}',
            "",
            'data: {"choices":[{"delta":{"content":" there"}}]}',
            "",
            'data: {"choices":[{"delta":{"content":"!"}}]}',
            "",
            "data: [DONE]",
        ]
        with patch(
            "tutor.services._chat.requests.post",
            return_value=_StreamingResponseStub(lines),
        ):
            out = list(chat_stream_tokens(self.conv, "Say hi"))
        self.assertEqual(out, ["Hi", " there", "!"])

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_done_sentinel_terminates(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"only"}}]}',
            "",
            "data: [DONE]",
            'data: {"choices":[{"delta":{"content":"NEVER"}}]}',  # ignored after [DONE]
        ]
        with patch(
            "tutor.services._chat.requests.post",
            return_value=_StreamingResponseStub(lines),
        ):
            out = list(chat_stream_tokens(self.conv, "x"))
        self.assertEqual(out, ["only"])

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_request_failure_yields_friendly_fallback(self):
        with patch(
            "tutor.services._chat.requests.post",
            side_effect=RuntimeError("boom"),
        ):
            out = list(chat_stream_tokens(self.conv, "hi"))
        self.assertEqual(len(out), 1)
        self.assertIn("temporarily unavailable", out[0].lower())

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_empty_stream_yields_nudge(self):
        # Some providers emit zero deltas (e.g. content filtered). The
        # generator must still yield *something* so the SSE bubble isn't
        # left blank.
        lines = ["data: [DONE]"]
        with patch(
            "tutor.services._chat.requests.post",
            return_value=_StreamingResponseStub(lines),
        ):
            out = list(chat_stream_tokens(self.conv, "x"))
        self.assertEqual(len(out), 1)
        self.assertIn("?", out[0])

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_voice_mode_caps_max_tokens(self):
        captured = {}

        def fake_post(url, **kwargs):
            # Only capture the FIRST call (the chat request). Post-chat
            # hooks (error analyzer) make their own requests.post calls
            # in tests with TUTOR_HOOKS_SYNC=True, which we don't want
            # overwriting the captured payload.
            if "payload" not in captured:
                captured["payload"] = kwargs.get("json")
            return _StreamingResponseStub(["data: [DONE]"])

        with patch("tutor.services._chat.requests.post", side_effect=fake_post):
            list(chat_stream_tokens(self.conv, "x", voice=True))
        self.assertEqual(captured["payload"]["max_tokens"], 70)
        self.assertTrue(captured["payload"]["stream"])

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_text_mode_uses_higher_token_cap(self):
        captured = {}

        def fake_post(url, **kwargs):
            # Only capture the FIRST call (the chat request). Post-chat
            # hooks (error analyzer) make their own requests.post calls
            # in tests with TUTOR_HOOKS_SYNC=True, which we don't want
            # overwriting the captured payload.
            if "payload" not in captured:
                captured["payload"] = kwargs.get("json")
            return _StreamingResponseStub(["data: [DONE]"])

        with patch("tutor.services._chat.requests.post", side_effect=fake_post):
            list(chat_stream_tokens(self.conv, "x"))
        self.assertEqual(captured["payload"]["max_tokens"], 130)
