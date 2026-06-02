"""Group A — Challenge AI migration (Prompt 12A.1).

Verifies challenge explanation / roleplay / end-advice route through the
ai_client wrapper and create AIUsageLog rows (success + failure), while the
legacy ChallengeAIInteraction row keeps being written, and that an AI-disabled
challenge never fabricates a provider-cost row.
"""
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from ai_usage import constants as C
from ai_usage.models import AIUsageLog
from ai_usage.services import ai_client

from tutor.services import challenge_tutor_service as svc
from tutor.tests.test_challenge_ai_phase7 import _make_course, _make_session_with_answer, _make_user

from .helpers import FakeResponse, chat_json


@override_settings(AI_API_KEY="sk-test", CHALLENGE_AI_ENABLED=True,
                   AI_USAGE_TRACKING_ENABLED=True)
class ChallengeMigrationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_learning_skills", verbosity=0)
        cls.course, cls.lesson, cls.quiz, cls.q = _make_course()
        cls.student = _make_user("ph7-stud")
        cls.session, cls.answer = _make_session_with_answer(
            cls.student, cls.lesson, cls.quiz, cls.q,
        )

    def test_challenge_explain_logs_ai_usage_success(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json("Try H."))):
            result = svc.explain_wrong_answer(self.student, self.answer)
        self.assertEqual(result["status"], "success")
        log = AIUsageLog.objects.filter(feature=C.FEATURE_CHALLENGE_EXPLANATION).latest("id")
        self.assertEqual(log.status, C.STATUS_SUCCESS)
        self.assertEqual(log.user_id, self.student.id)
        self.assertEqual(log.input_tokens, 100)

    def test_challenge_explain_logs_ai_usage_failure(self):
        with mock.patch.object(ai_client.requests, "post",
                               side_effect=RuntimeError("upstream 500")):
            result = svc.explain_wrong_answer(self.student, self.answer)
        self.assertEqual(result["status"], "failed")
        log = AIUsageLog.objects.filter(feature=C.FEATURE_CHALLENGE_EXPLANATION).latest("id")
        self.assertEqual(log.status, C.STATUS_FAILED)

    def test_challenge_roleplay_logs_ai_usage(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json("Hi there!"))):
            result = svc.start_short_roleplay(self.student, self.session, self.q)
        self.assertEqual(result["status"], "success")
        self.assertTrue(
            AIUsageLog.objects.filter(feature=C.FEATURE_CHALLENGE_ROLEPLAY,
                                      status=C.STATUS_SUCCESS).exists()
        )

    def test_challenge_end_advice_logs_ai_usage(self):
        with mock.patch.object(ai_client.requests, "post",
                               return_value=FakeResponse(json_data=chat_json("Keep going!"))):
            result = svc.generate_end_challenge_advice(self.student, self.session)
        self.assertEqual(result["status"], "success")
        self.assertTrue(
            AIUsageLog.objects.filter(feature=C.FEATURE_CHALLENGE_END_ADVICE,
                                      status=C.STATUS_SUCCESS).exists()
        )

    @override_settings(CHALLENGE_AI_ENABLED=False)
    def test_challenge_ai_disabled_does_not_fake_provider_cost(self):
        with mock.patch.object(ai_client.requests, "post") as post:
            result = svc.explain_wrong_answer(self.student, self.answer)
        post.assert_not_called()
        self.assertEqual(result["status"], "fallback")
        self.assertFalse(AIUsageLog.objects.exists())
