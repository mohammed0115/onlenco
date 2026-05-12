"""Plans should reflect the student's weaknesses + recent mistakes."""
from __future__ import annotations

from django.test import TestCase
from django.utils import timezone

from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class WeaknessAndMistakesTests(TestCase):
    def setUp(self):
        from learning_core.models import (
            GrammarTopic, Skill, UserError, UserWeakness,
        )
        self.GrammarTopic = GrammarTopic
        self.Skill = Skill
        self.UserError = UserError
        self.UserWeakness = UserWeakness

    def test_recent_mistakes_become_review_items(self):
        user = make_student(username="mistakeu", cefr_level="A2")
        self.UserError.objects.create(
            user=user,
            source_type="quiz",
            original_text="I goes to school.",
            corrected_text="I go to school.",
            error_type="grammar",
            severity=7,
            explanation="With \"I\" we use the base verb.",
        )
        plan = generate_for_user(user)
        review_items = list(plan.items.filter(item_type="review_mistake"))
        self.assertEqual(len(review_items), 1)
        self.assertIn("I go to school.", review_items[0].correct_answer)

    def test_high_priority_weakness_triggers_weakness_review_plan(self):
        user = make_student(username="weaku", cefr_level="A2")
        skill = self.Skill.objects.create(
            name="Past Simple Skill", category="grammar", cefr_level="A2",
        )
        topic = self.GrammarTopic.objects.create(
            name="Past Simple", slug="past-simple-test", cefr_level="A2",
        )
        self.UserWeakness.objects.create(
            user=user, skill=skill, grammar_topic=topic,
            weakness_score=80.0, priority_score=9.0,
            frequency=5, severity_average=7.0, status="active",
        )
        plan = generate_for_user(user)
        self.assertEqual(plan.plan_type, "weakness_review")
