from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from learning_core.models import (
    Skill,
    StudentLearningProfile,
    UserError,
    UserWeakness,
)
from tutor.models import TutorConversation
from tutor.services import chat
from tutor.services.context_builder import build_tutor_context, render_context_block

User = get_user_model()


class TutorContextBuilderTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lia", password="pw")
        self.user.profile.cefr_level = "B1"
        self.user.profile.preferred_language = "ar"
        self.user.profile.save()
        self.skill = Skill.objects.create(name="Grammar core", category="grammar", cefr_level="B1")
        StudentLearningProfile.objects.create(
            user=self.user, current_cefr_level="B1", theta_score=0.0
        )
        UserWeakness.objects.create(
            user=self.user, skill=self.skill, weakness_score=50, priority_score=50, status="active"
        )
        UserError.objects.create(
            user=self.user,
            source_type="quiz",
            original_text="I goes",
            error_type="grammar",
            severity=6,
            explanation="Subject-verb",
        )

    def test_context_includes_cefr_and_language(self):
        ctx = build_tutor_context(self.user, conversation_topic="Past tense")
        self.assertEqual(ctx["cefr_level"], "B1")
        self.assertEqual(ctx["language_preference"], "ar")
        self.assertEqual(ctx["topic"], "Past tense")
        self.assertGreaterEqual(len(ctx["top_weaknesses"]), 1)
        self.assertGreaterEqual(len(ctx["recent_errors"]), 1)

    def test_render_context_block_short_and_safe(self):
        ctx = build_tutor_context(self.user)
        text = render_context_block(ctx)
        self.assertIn("CEFR level: B1", text)
        self.assertIn("Top weaknesses", text)
        self.assertNotIn(self.user.password, text)


class TutorChatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dan", password="pw")
        self.conv = TutorConversation.objects.create(user=self.user, topic="general")

    @override_settings(AI_API_KEY="")
    def test_no_api_key_returns_stub_and_logs_error(self):
        reply = chat(self.conv, "I goes home")
        self.assertIn("stub", reply)
        # Error analyzer ran (heuristic) → UserError exists
        self.assertGreaterEqual(
            UserError.objects.filter(user=self.user, source_type="tutor").count(), 1
        )

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_ai_failure_returns_fallback_message(self):
        from tutor.services import _chat

        with patch.object(_chat.requests, "post", side_effect=RuntimeError("boom")):
            reply = chat(self.conv, "Tell me about past tense")
        self.assertIn("temporarily unavailable", reply.lower())

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_ai_success_returns_content(self):
        from tutor.services import _chat

        class R:
            status_code = 200

            def json(self_inner):
                return {
                    "choices": [
                        {"message": {"content": "Past simple is for finished actions. Got it?"}}
                    ]
                }

            def raise_for_status(self_inner):
                pass

        with patch.object(_chat.requests, "post", return_value=R()):
            reply = chat(self.conv, "What is past simple?")
        self.assertIn("Past simple", reply)
