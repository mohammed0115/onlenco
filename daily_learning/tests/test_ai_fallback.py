"""AI prompt + fallback behavior."""
from __future__ import annotations

from unittest import mock

from django.test import TestCase, override_settings

from daily_learning.services import ai_prompts
from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class AIValidationTests(TestCase):
    def test_validate_rejects_garbage(self):
        self.assertIsNone(ai_prompts.validate_ai_output("not json"))
        self.assertIsNone(ai_prompts.validate_ai_output(None))
        self.assertIsNone(ai_prompts.validate_ai_output({}))

    def test_validate_rejects_underscore_banned(self):
        bad = {
            "title": "Fill the blank blank blank",
            "description": "ok",
            "motivation_message": "Great",
            "items": [
                {"item_type": "quiz", "title": "underscore", "instructions": "x"},
            ] * 5,
        }
        self.assertIsNone(ai_prompts.validate_ai_output(bad))

    def test_validate_accepts_well_formed(self):
        good = {
            "title": "Today's plan",
            "description": "A short plan",
            "motivation_message": "Great work today!",
            "items": [
                {
                    "item_type": "vocabulary",
                    "title": f"Item {i}",
                    "instructions": "Read each word.",
                    "content_text": "name — اسم",
                    "skill": "vocabulary",
                    "difficulty_score": 0.2,
                }
                for i in range(5)
            ],
        }
        cleaned = ai_prompts.validate_ai_output(good)
        self.assertIsNotNone(cleaned)
        self.assertEqual(len(cleaned["items"]), 5)


class AIFallbackTests(TestCase):
    @override_settings(DAILY_LEARNING_USE_AI=True, DAILY_LEARNING_AI_DAILY_CAP_PER_USER=1)
    def test_ai_failure_does_not_break_plan(self):
        """When AI raises, generator still produces a valid plan."""
        user = make_student(username="aifail", cefr_level="A1")
        with mock.patch(
            "ai_engine.services.model_router.route_task",
            side_effect=Exception("boom"),
        ):
            plan = generate_for_user(user)
        self.assertGreaterEqual(plan.items.count(), 5)
