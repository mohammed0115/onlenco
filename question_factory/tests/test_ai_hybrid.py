"""Cover the AI + Hybrid generators with mocks so no real LLM call happens."""
import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from question_factory import constants as C
from question_factory.models import GeneratedQuestion, QuestionBlueprint
from question_factory.services import ai_generator, hybrid_generator


def _bp() -> QuestionBlueprint:
    return QuestionBlueprint.objects.create(
        code="t-ai", title="t",
        cefr_level="A1", skill=C.SKILL_GRAMMAR,
        question_type="multiple_choice",
        template_pattern="{subject} ___ to school every day.",
        expected_answer_pattern="verb.0 + 's'",
        explanation_pattern="Use '{verb.0}s' with '{subject}'.",
        variables_schema={
            "subject": ["she", "he"],
            "verb": [["walk", "walked"], ["play", "played"]],
        },
        metadata={"distractor_config": {"strategy": "morph"}},
    )


@override_settings(AI_API_KEY="sk-test", AI_LOCAL_API_BASE="")
class AIGeneratorTests(TestCase):
    def test_no_payload_returns_zero(self):
        bp = _bp()
        with patch("factory.services.llm_router.chat", return_value=None):
            stats = ai_generator.generate_for_blueprint(bp, count=2)
        self.assertEqual(stats["accepted"], 0)
        self.assertEqual(GeneratedQuestion.objects.count(), 0)

    def test_valid_payload_persists(self):
        bp = _bp()
        payload = {
            "_router": {"served_by": "openai"},
            "choices": [{"message": {"content": json.dumps({
                "questions": [{
                    "question_text": "She ___ to school every day.",
                    "options": ["go", "goes", "going", "gone"],
                    "correct_answer": "goes",
                    "explanation": "3rd-person singular adds -s.",
                    "feedback_correct": "Nice!",
                    "feedback_wrong": "Try again.",
                    "acceptable_answers": ["goes"],
                }]
            })}}]
        }
        with patch("factory.services.llm_router.chat", return_value=payload):
            stats = ai_generator.generate_for_blueprint(bp, count=1)
        self.assertEqual(stats["accepted"], 1)
        self.assertEqual(stats["served_by"], "openai")
        item = GeneratedQuestion.objects.get()
        self.assertEqual(item.generated_by, C.GEN_AI)
        self.assertTrue(item.metadata.get("validation"))


@override_settings(AI_API_KEY="sk-test", AI_LOCAL_API_BASE="")
class HybridGeneratorTests(TestCase):
    def test_hybrid_falls_back_to_template_when_ai_unavailable(self):
        bp = _bp()
        with patch("factory.services.llm_router.chat", return_value=None):
            stats = hybrid_generator.generate_for_blueprint(bp, count=3)
        # AI didn't help, but the template body is still valid → items persist
        # with the template's explanation.
        self.assertGreater(stats["accepted"], 0)
        self.assertEqual(stats["ai_used"], 0)
        for it in GeneratedQuestion.objects.all():
            self.assertEqual(it.generated_by, C.GEN_HYBRID)

    def test_hybrid_uses_ai_explanation_when_available(self):
        bp = _bp()
        payload = {
            "choices": [{"message": {"content": json.dumps({
                "explanation": "We add -s to verbs in the third person singular.",
            })}}]
        }
        with patch("factory.services.llm_router.chat", return_value=payload):
            stats = hybrid_generator.generate_for_blueprint(bp, count=2)
        self.assertEqual(stats["ai_used"], 2)
        for it in GeneratedQuestion.objects.all():
            self.assertIn("third person singular", it.explanation)
