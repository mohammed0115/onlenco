from unittest.mock import patch

from django.test import TestCase, override_settings

from exams.services import ai_question_generator
from exams.services.template_question_generator import generate, generate_unique


class TemplateGeneratorTests(TestCase):
    def test_small_batch_yields_items(self):
        items = generate("A1", count=20, seed=1)
        self.assertEqual(len(items), 20)
        for it in items:
            self.assertEqual(it["cefr_level"], "A1")
            self.assertTrue(it["question"])
            self.assertTrue(it["correct_answer"])
            self.assertTrue(it["code"])
            self.assertTrue(it["text_hash"])

    def test_codes_are_unique_within_batch(self):
        items = generate_unique("A2", target=30)
        codes = {i["code"] for i in items}
        self.assertEqual(len(codes), len(items))

    def test_single_skill_filter(self):
        items = generate("A1", skill="vocabulary", count=10, seed=2)
        for it in items:
            self.assertEqual(it["metadata"]["topic"] in
                             {"vocab_definitions", "antonyms"}, True)


class AIGeneratorFallbackTests(TestCase):
    @override_settings(AI_API_KEY="")
    def test_no_key_returns_empty(self):
        out = ai_question_generator.generate(
            cefr_level="A1", skill="grammar", count=3,
        )
        self.assertEqual(out, [])

    @override_settings(AI_API_KEY="sk-test")
    def test_network_failure_returns_empty(self):
        with patch.object(ai_question_generator.requests, "post",
                          side_effect=RuntimeError("net")):
            out = ai_question_generator.generate(
                cefr_level="A1", skill="grammar", count=3,
            )
        self.assertEqual(out, [])

    @override_settings(AI_API_KEY="sk-test")
    def test_malformed_response_returns_empty(self):
        fake = type("R", (), {})()
        fake.raise_for_status = lambda: None
        fake.json = lambda: {"choices": [{"message": {"content": "not-json"}}]}
        with patch.object(ai_question_generator.requests, "post", return_value=fake):
            out = ai_question_generator.generate(
                cefr_level="A1", skill="grammar", count=3,
            )
        self.assertEqual(out, [])

    @override_settings(AI_API_KEY="sk-test")
    def test_successful_response_parses_to_bank_dict(self):
        """When the LLM returns the expected JSON envelope, the generator
        should yield bank-shaped dicts with quality_score, text_hash, code,
        generated_by='ai', is_reviewed=False, etc."""
        import json as _json
        payload = {
            "questions": [
                {
                    "question_text": "She ___ to school every day.",
                    "instructions": "Choose the correct verb form.",
                    "options": ["go", "goes", "going", "gone"],
                    "correct_answer": "goes",
                    "acceptable_answers": ["goes"],
                    "explanation": "Third person singular present takes 's'.",
                    "feedback_correct": "Nice!",
                    "feedback_wrong": "Try again.",
                    "difficulty_score": 0.3,
                    "cefr_level": "A1",
                    "skill": "grammar",
                    "question_type": "multiple_choice",
                    "grammar_topic": "present_simple",
                },
            ]
        }
        fake = type("R", (), {})()
        fake.raise_for_status = lambda: None
        fake.json = lambda: {
            "choices": [{"message": {"content": _json.dumps(payload)}}]
        }
        with patch.object(ai_question_generator.requests, "post", return_value=fake):
            out = ai_question_generator.generate(
                cefr_level="A1", skill="grammar", count=1,
            )
        self.assertEqual(len(out), 1)
        item = out[0]
        self.assertEqual(item["question"], "She ___ to school every day.")
        self.assertEqual(item["correct_answer"], "goes")
        self.assertEqual(item["generated_by"], "ai")
        self.assertTrue(item["generated_by_ai"])
        self.assertFalse(item["is_reviewed"])  # AI items must be reviewed
        self.assertTrue(item["text_hash"])
        self.assertTrue(item["code"].startswith("ai:A1:grammar:multiple_choice:"))
        self.assertGreaterEqual(item["quality_score"], 60)
