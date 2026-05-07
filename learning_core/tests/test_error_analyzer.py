from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from learning_core.models import GrammarTopic, Skill, UserError
from learning_core.services import error_analyzer

User = get_user_model()


def _fake_response(payload: dict, status: int = 200):
    class R:
        status_code = status

        def json(self_inner):
            return payload

        def raise_for_status(self_inner):
            if status >= 400:
                raise RuntimeError("bad status")

    return R()


def _ai_envelope(args: dict) -> dict:
    import json
    return {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"function": {"arguments": json.dumps(args)}}
                    ]
                }
            }
        ]
    }


class ErrorAnalyzerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bob", password="pw")
        self.grammar_skill = Skill.objects.create(
            name="Grammar core", category="grammar", cefr_level="A2"
        )
        self.topic = GrammarTopic.objects.create(
            name="Subject-verb agreement",
            slug="subject-verb-agreement",
            cefr_level="A2",
        )

    @override_settings(AI_API_KEY="test-key", AI_API_BASE="https://x", AI_MODEL="m")
    def test_ai_success_creates_user_errors(self):
        ai_args = {
            "original_text": "I goes home",
            "corrected_text": "I go home",
            "errors": [
                {
                    "error_type": "grammar",
                    "original_fragment": "I goes",
                    "corrected_fragment": "I go",
                    "grammar_topic": "Subject-verb agreement",
                    "skill_category": "grammar",
                    "severity": 6,
                    "explanation": "Subject 'I' takes 'go'.",
                    "confidence": 0.95,
                }
            ],
        }
        with patch.object(
            error_analyzer.requests,
            "post",
            return_value=_fake_response(_ai_envelope(ai_args)),
        ):
            result = error_analyzer.analyze_text(
                self.user, "I goes home", source_type="quiz"
            )

        self.assertEqual(len(result["errors"]), 1)
        ue = UserError.objects.get(user=self.user)
        self.assertEqual(ue.error_type, "grammar")
        self.assertEqual(ue.skill, self.grammar_skill)
        self.assertEqual(ue.grammar_topic, self.topic)
        self.assertEqual(ue.source_type, "quiz")

    @override_settings(AI_API_KEY="test-key", AI_API_BASE="https://x", AI_MODEL="m")
    def test_ai_malformed_response_falls_back(self):
        # Missing 'errors' key => invalid → fallback heuristic should run
        with patch.object(
            error_analyzer.requests,
            "post",
            return_value=_fake_response(_ai_envelope({"original_text": "x"})),
        ):
            result = error_analyzer.analyze_text(self.user, "I goes home")
        # heuristic catches "I goes"
        self.assertTrue(any(e["error_type"] == "grammar" for e in result["errors"]))
        self.assertGreaterEqual(UserError.objects.filter(user=self.user).count(), 1)

    @override_settings(AI_API_KEY="")
    def test_no_api_key_uses_fallback(self):
        result = error_analyzer.analyze_text(self.user, "I goes home")
        types = {e["error_type"] for e in result["errors"]}
        self.assertIn("grammar", types)
        self.assertEqual(
            UserError.objects.filter(user=self.user, error_type="grammar").count(), 1
        )

    @override_settings(AI_API_KEY="")
    def test_empty_text_returns_empty(self):
        result = error_analyzer.analyze_text(self.user, "   ")
        self.assertEqual(result["errors"], [])
        self.assertFalse(UserError.objects.filter(user=self.user).exists())

    @override_settings(AI_API_KEY="test-key", AI_API_BASE="https://x", AI_MODEL="m")
    def test_ai_network_failure_falls_back(self):
        with patch.object(
            error_analyzer.requests, "post", side_effect=RuntimeError("boom")
        ):
            result = error_analyzer.analyze_text(self.user, "teh cat sat")
        # heuristic should catch "teh"
        self.assertTrue(any(e["error_type"] == "spelling" for e in result["errors"]))

    @override_settings(AI_API_KEY="")
    def test_invalid_source_type_is_normalized(self):
        error_analyzer.analyze_text(self.user, "I goes home", source_type="bogus")
        ue = UserError.objects.filter(user=self.user).first()
        self.assertEqual(ue.source_type, "writing")
