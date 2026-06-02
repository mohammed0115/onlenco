from unittest import mock

from django.test import TestCase, override_settings

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client

from .helpers import FakeResponse, chat_json, make_user, sse_lines


@override_settings(AI_API_KEY="sk-test-key", AI_USAGE_TRACKING_ENABLED=True)
class WrapperTests(TestCase):
    def test_successful_ai_request_logs_usage(self):
        u = make_user()
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json())) as post:
            data = ai_client.chat(
                [{"role": "user", "content": "hi"}],
                user=u, feature=C.FEATURE_AI_TUTOR, model="gpt-4o-mini",
            )
        post.assert_called_once()
        self.assertEqual(data["choices"][0]["message"]["content"], "hello")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.status, C.STATUS_SUCCESS)
        self.assertEqual(log.input_tokens, 100)
        self.assertEqual(log.output_tokens, 50)
        self.assertEqual(log.feature, C.FEATURE_AI_TUTOR)

    def test_wrapper_preserves_existing_response(self):
        payload = chat_json(content="exact-passthrough")
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=payload)):
            data = ai_client.chat([{"role": "user", "content": "x"}],
                                  feature="other", model="gpt-4o-mini")
        self.assertEqual(data, payload)

    def test_failed_ai_request_logs_usage(self):
        with mock.patch.object(ai_client.requests, "post",
                               side_effect=RuntimeError("upstream 500")):
            with self.assertRaises(RuntimeError):
                ai_client.chat([{"role": "user", "content": "x"}],
                               feature="other", model="gpt-4o-mini")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.status, C.STATUS_FAILED)
        self.assertIn("upstream 500", log.error_message)

    def test_streaming_ai_request_logs_usage(self):
        resp = FakeResponse(lines=sse_lines())
        with mock.patch.object(ai_client.requests, "post", return_value=resp):
            chunks = list(ai_client.stream_chat(
                [{"role": "user", "content": "x"}], feature="other", model="gpt-4o-mini",
            ))
        self.assertEqual("".join(chunks), "Hello")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.status, C.STATUS_SUCCESS)
        self.assertEqual(log.input_tokens, 10)
        self.assertEqual(log.output_tokens, 2)

    def test_wrapper_does_not_expose_api_key(self):
        # An exception that embeds the key must be scrubbed before logging.
        with mock.patch.object(ai_client.requests, "post",
                               side_effect=RuntimeError("auth failed for sk-test-key")):
            with self.assertRaises(RuntimeError):
                ai_client.chat([{"role": "user", "content": "x"}],
                               feature="other", model="gpt-4o-mini")
        log = AIUsageLog.objects.get()
        self.assertNotIn("sk-test-key", log.error_message)
        self.assertIn("***", log.error_message)

    def test_transcribe_logs_audio_seconds(self):
        resp = FakeResponse(json_data={"text": "hi there", "duration": 12.4})
        with mock.patch.object(ai_client.requests, "post", return_value=resp):
            data = ai_client.transcribe_audio(b"bytes", feature=C.FEATURE_PLACEMENT_SPEAKING,
                                              model="whisper-1")
        self.assertEqual(data["text"], "hi there")
        log = AIUsageLog.objects.get()
        self.assertEqual(log.audio_input_seconds, 12)

    def test_minute_enforcement_blocks_when_exhausted(self):
        u = make_user()
        with mock.patch("ai_usage.services.limit_service.check_can_start_ai_tutor",
                        return_value=(False, {"reason": "x", "message": {"ar": "a", "en": "e"}})):
            with self.assertRaises(ai_client.DailyMinutesExceeded):
                ai_client.chat([{"role": "user", "content": "x"}], user=u,
                               feature=C.FEATURE_AI_TUTOR, enforce_minutes=True)
