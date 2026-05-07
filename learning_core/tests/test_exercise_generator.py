import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from learning_core.models import (
    AdaptiveExercise,
    GrammarTopic,
    Skill,
    UserError,
    UserWeakness,
)
from learning_core.services import exercise_generator
from learning_core.services.weakness_engine import update_user_weaknesses

User = get_user_model()


def _ai_envelope(args: dict) -> dict:
    return {
        "choices": [
            {"message": {"tool_calls": [{"function": {"arguments": json.dumps(args)}}]}}
        ]
    }


def _fake_response(payload, status=200):
    class R:
        status_code = status

        def json(self_inner):
            return payload

        def raise_for_status(self_inner):
            if status >= 400:
                raise RuntimeError("bad status")

    return R()


class ExerciseGeneratorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ali", password="pw")
        self.grammar = Skill.objects.create(
            name="Grammar core", category="grammar", cefr_level="A2"
        )
        self.topic = GrammarTopic.objects.create(
            name="Past Simple", slug="past-simple", cefr_level="A2"
        )
        # Seed enough errors to create a weakness
        for _ in range(4):
            UserError.objects.create(
                user=self.user,
                source_type="quiz",
                error_type="grammar",
                skill=self.grammar,
                grammar_topic=self.topic,
                severity=7,
            )
        update_user_weaknesses(self.user)

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_ai_success_creates_adaptive_exercises(self):
        ai_args = {
            "exercises": [
                {
                    "question_type": "multiple_choice",
                    "question": "She ___ to school yesterday.",
                    "options": ["go", "goes", "went", "gone"],
                    "correct_answer": "went",
                    "explanation": "Past simple of 'go'.",
                    "skill": "grammar",
                    "grammar_topic": "Past Simple",
                    "cefr_level": "A2",
                    "difficulty_score": 0.4,
                }
            ]
        }
        with patch.object(
            exercise_generator.requests,
            "post",
            return_value=_fake_response(_ai_envelope(ai_args)),
        ):
            saved = exercise_generator.generate_personalized_exercises(
                self.user, count_per_weakness=1
            )
        self.assertGreaterEqual(len(saved), 1)
        ex = saved[0]
        self.assertTrue(ex.generated_by_ai)
        self.assertEqual(ex.skill, self.grammar)
        self.assertEqual(ex.topic, self.topic)
        self.assertEqual(ex.metadata.get("prompt_version"), exercise_generator.PROMPT_VERSION)

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_malformed_ai_response_falls_back(self):
        with patch.object(
            exercise_generator.requests,
            "post",
            return_value=_fake_response(_ai_envelope({"wrong": "shape"})),
        ):
            saved = exercise_generator.generate_personalized_exercises(
                self.user, count_per_weakness=1
            )
        self.assertGreaterEqual(len(saved), 1)
        self.assertFalse(saved[0].generated_by_ai)

    @override_settings(AI_API_KEY="")
    def test_no_api_key_uses_template_fallback(self):
        saved = exercise_generator.generate_personalized_exercises(
            self.user, count_per_weakness=2
        )
        self.assertGreaterEqual(len(saved), 1)
        self.assertTrue(all(not e.generated_by_ai for e in saved))

    @override_settings(AI_API_KEY="")
    def test_no_weaknesses_returns_warmup_batch(self):
        # Make a fresh user with no weaknesses
        u2 = User.objects.create_user(username="zen", password="pw")
        saved = exercise_generator.generate_personalized_exercises(u2, count_per_weakness=2)
        self.assertGreaterEqual(len(saved), 1)
        # Warm-up batch is not associated with any specific skill/topic
        self.assertTrue(all(e.skill is None and e.topic is None for e in saved))

    @override_settings(AI_API_KEY="")
    def test_no_duplicate_question_in_same_run(self):
        # Run twice in the same call path: ensure distinct questions in one call
        saved = exercise_generator.generate_personalized_exercises(
            self.user, count_per_weakness=3
        )
        questions = [e.question for e in saved]
        self.assertEqual(len(set(questions)), len(questions))

    @override_settings(AI_API_KEY="k", AI_API_BASE="https://x", AI_MODEL="m")
    def test_ai_network_failure_falls_back(self):
        with patch.object(
            exercise_generator.requests, "post", side_effect=RuntimeError("network")
        ):
            saved = exercise_generator.generate_personalized_exercises(
                self.user, count_per_weakness=1
            )
        self.assertGreaterEqual(len(saved), 1)
        self.assertFalse(saved[0].generated_by_ai)
