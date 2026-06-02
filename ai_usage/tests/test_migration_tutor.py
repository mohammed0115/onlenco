"""Group B — Tutor text + streaming migration (Prompt 12A.1)."""
from unittest import mock

from django.test import TestCase, override_settings

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client, limit_service

from tutor.models import TutorConversation
from tutor.services import _chat

from .helpers import FakeResponse, chat_json, give_plan, make_user, sse_lines


@override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True)
class TutorMigrationTests(TestCase):
    def setUp(self):
        self.user = make_user("tutoru")
        self.conv = TutorConversation.objects.create(user=self.user, topic="grammar")

    def test_tutor_text_call_logs_usage(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json("Hi!"))):
            reply = _chat.chat(self.conv, "hello")
        self.assertTrue(reply)
        log = AIUsageLog.objects.filter(feature=C.FEATURE_AI_TUTOR).get()
        self.assertEqual(log.status, C.STATUS_SUCCESS)
        self.assertEqual(log.input_tokens, 100)
        self.assertEqual(log.user_id, self.user.id)

    def test_tutor_stream_call_logs_usage_when_usage_available(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(lines=sse_lines())):
            out = list(_chat.chat_stream_tokens(self.conv, "hello"))
        self.assertEqual("".join(out), "Hello")
        log = AIUsageLog.objects.filter(feature=C.FEATURE_AI_TUTOR).get()
        self.assertEqual(log.status, C.STATUS_SUCCESS)
        self.assertEqual(log.input_tokens, 10)
        self.assertEqual(log.output_tokens, 2)

    def test_tutor_stream_logs_zero_tokens_with_note_when_usage_missing(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(lines=sse_lines(with_usage=False))):
            out = list(_chat.chat_stream_tokens(self.conv, "hello"))
        self.assertEqual("".join(out), "Hello")
        log = AIUsageLog.objects.filter(feature=C.FEATURE_AI_TUTOR).get()
        self.assertEqual(log.status, C.STATUS_SUCCESS)
        self.assertEqual(log.total_tokens, 0)
        self.assertTrue(log.metadata.get("stream_usage_unavailable"))

    def test_tutor_failed_call_logs_usage(self):
        with mock.patch.object(ai_client.requests, "post",
                               side_effect=RuntimeError("boom")):
            reply = _chat.chat(self.conv, "hello")
        # Caller still gets a friendly fallback…
        self.assertIn("trouble", reply)
        # …and the failure is logged.
        log = AIUsageLog.objects.filter(feature=C.FEATURE_AI_TUTOR).get()
        self.assertEqual(log.status, C.STATUS_FAILED)

    def test_tutor_minutes_enforced(self):
        # Speaking-session enforcement: when minutes are out, the wrapper
        # blocks before any provider call.
        student = make_user("nominutes")
        with mock.patch("ai_usage.services.limit_service.check_can_start_ai_tutor",
                        return_value=(False, {"reason": "daily_minutes_exhausted",
                                              "message": {"ar": "x", "en": "y"}})):
            with mock.patch.object(ai_client.requests, "post") as post:
                with self.assertRaises(ai_client.DailyMinutesExceeded):
                    ai_client.chat([{"role": "user", "content": "hi"}], user=student,
                                   feature=C.FEATURE_AI_TUTOR, enforce_minutes=True)
            post.assert_not_called()

    def test_tutor_actual_duration_updates_minutes(self):
        student = make_user("dur2")
        give_plan(student, 10)
        row = limit_service.finalize_ai_tutor_minutes(student, 3)
        self.assertEqual(str(row.used_minutes), "3.00")
        self.assertEqual(str(row.remaining_minutes), "7.00")
