"""Group E — Teacher/admin content generation + funnel migration (12A.1)."""
import json
from unittest import mock

from django.test import TestCase, override_settings

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client

from .helpers import FakeResponse, chat_json, make_user


def _tool_json(name="produce", payload=None):
    args = json.dumps(payload or {"exercises": []})
    return {
        "choices": [{"message": {"tool_calls": [
            {"function": {"name": name, "arguments": args}}]}}],
        "usage": {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60},
    }


@override_settings(AI_API_KEY="sk-test", AI_USAGE_TRACKING_ENABLED=True)
class ContentGenerationMigrationTests(TestCase):
    def test_teacher_content_generation_logs_usage(self):
        teacher = make_user("t1", role="teacher")
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json("ok"))):
            ai_client.generate_content(
                [{"role": "user", "content": "make a quiz"}],
                user=teacher, role=C.ROLE_TEACHER,
                feature=C.FEATURE_CONTENT_GENERATION, model="gpt-4o-mini",
            )
        log = AIUsageLog.objects.get()
        self.assertEqual(log.role, C.ROLE_TEACHER)
        self.assertEqual(log.feature, C.FEATURE_CONTENT_GENERATION)

    def test_admin_content_generation_logs_usage(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json("ok"))):
            ai_client.generate_content(
                [{"role": "user", "content": "x"}], role=C.ROLE_ADMIN,
                feature=C.FEATURE_CONTENT_GENERATION, model="gpt-4o-mini",
            )
        log = AIUsageLog.objects.get()
        self.assertEqual(log.role, C.ROLE_ADMIN)

    def test_content_generation_not_counted_against_student_minutes(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json("ok"))):
            ai_client.generate_content(
                [{"role": "user", "content": "x"}], role=C.ROLE_SYSTEM,
                feature=C.FEATURE_CONTENT_GENERATION, model="gpt-4o-mini",
            )
        log = AIUsageLog.objects.get()
        self.assertEqual(log.ai_minutes_used, 0)
        self.assertNotIn(C.FEATURE_CONTENT_GENERATION, C.MINUTE_BEARING_FEATURES)

    def test_content_generation_failure_logged(self):
        with mock.patch.object(ai_client.requests, "post",
                               side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                ai_client.generate_content(
                    [{"role": "user", "content": "x"}], role=C.ROLE_SYSTEM,
                    feature=C.FEATURE_CONTENT_GENERATION, model="gpt-4o-mini",
                )
        log = AIUsageLog.objects.get()
        self.assertEqual(log.status, C.STATUS_FAILED)

    def test_migrated_exercise_generator_logs_usage(self):
        from learning_core.services import exercise_generator
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=_tool_json())):
            exercise_generator._call_ai(skill="grammar", topic="past",
                                        cefr_level="A2", difficulty=0.4, count=2)
        log = AIUsageLog.objects.get()
        self.assertEqual(log.feature, C.FEATURE_CONTENT_GENERATION)
        self.assertEqual(log.role, C.ROLE_SYSTEM)
        self.assertEqual(log.input_tokens, 40)

    def test_funnel_llm_router_logs_usage(self):
        from factory.services import llm_router
        with mock.patch.object(llm_router.requests, "post",
                               return_value=FakeResponse(json_data=chat_json("hi"))):
            out = llm_router.chat([{"role": "user", "content": "x"}], prefer="openai")
        self.assertIsNotNone(out)
        log = AIUsageLog.objects.filter(feature=C.FEATURE_CONTENT_GENERATION).latest("id")
        self.assertEqual(log.metadata.get("via"), "llm_router_funnel")
        self.assertEqual(log.role, C.ROLE_SYSTEM)
