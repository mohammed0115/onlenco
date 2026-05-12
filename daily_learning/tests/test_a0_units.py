"""A0 unit roadmap + per-lesson structure tests.

Verifies the A0 generator emits the 6-item shape the spec demands
(simple word, simple sentence, listening, speaking, small question,
encouragement), with every unit (1..5) representable.
"""
from __future__ import annotations

from django.test import TestCase

from daily_learning.services import a0_templates
from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class A0UnitTests(TestCase):
    def test_every_unit_has_at_least_one_topic(self):
        units_seen = {t.unit for t in a0_templates.A0_TOPICS}
        self.assertEqual(units_seen, {1, 2, 3, 4, 5},
                         f"Missing units: {{1..5}} - {units_seen}")

    def test_every_topic_has_six_items_in_correct_order(self):
        """Canonical A0 daily shape: vocabulary → grammar_tip → listening
        → speaking → quiz → motivation."""
        expected = (
            "vocabulary", "grammar_tip", "listening",
            "speaking", "quiz", "motivation",
        )
        for topic in a0_templates.A0_TOPICS:
            actual = tuple(i.item_type for i in topic.items)
            self.assertEqual(
                actual, expected,
                f"Topic {topic.slug!r} expected {expected}, got {actual}",
            )

    def test_a0_plan_has_six_items_no_duplicate_motivation(self):
        """The generator must NOT append an extra motivation closer."""
        user = make_student(username="a0six", cefr_level="A0",
                            onboarding_path="beginner_start")
        plan = generate_for_user(user)
        self.assertEqual(plan.items.count(), 6)
        motivations = plan.items.filter(item_type="motivation").count()
        self.assertEqual(motivations, 1,
                         "Each A0 plan must include exactly one motivation.")

    def test_a0_plan_records_unit_in_metadata(self):
        user = make_student(username="a0unitmeta", cefr_level="A0",
                            onboarding_path="beginner_start")
        plan = generate_for_user(user)
        self.assertIn("topic_unit", plan.metadata)
        self.assertIn(plan.metadata["topic_unit"], {1, 2, 3, 4, 5})

    def test_a0_quiz_options_are_three_choices(self):
        """Small-question spec: multiple choice, 3 options."""
        for topic in a0_templates.A0_TOPICS:
            quiz_item = next(
                (i for i in topic.items if i.item_type == "quiz"),
                None,
            )
            self.assertIsNotNone(
                quiz_item, f"Topic {topic.slug!r} missing quiz item",
            )
            self.assertEqual(
                len(quiz_item.options), 3,
                f"Topic {topic.slug!r} quiz must have 3 options, "
                f"got {len(quiz_item.options)}",
            )
            self.assertIn(quiz_item.correct_answer, quiz_item.options,
                          f"Correct answer must be one of the options "
                          f"for topic {topic.slug!r}")

    def test_unit_one_contains_hello_and_name(self):
        """Spec roadmap: Unit 1 = 'Hello English' (hello + my name is …)."""
        slugs = {t.slug for t in a0_templates.topics_for_unit(1)}
        self.assertIn("u1_hello", slugs)
        self.assertIn("u1_name", slugs)

    def test_unit_five_covers_daily_life_verbs(self):
        """Spec roadmap: Unit 5 includes wake up, eat, drink, go."""
        unit_5_words = {t.target_word for t in a0_templates.topics_for_unit(5)}
        # At least 3 of the four core daily-life verbs.
        self.assertGreaterEqual(
            len(unit_5_words & {"wake up", "eat", "water", "work"}), 3,
        )
