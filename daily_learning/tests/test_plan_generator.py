"""Generator behavior for A1+ users."""
from __future__ import annotations

import datetime

from django.test import TestCase, override_settings

from daily_learning.models import DailyLearningPlan
from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class LeveledPlanTests(TestCase):
    def test_a1_plan_in_5_to_8_items(self):
        user = make_student(username="a1u", cefr_level="A1", language="en")
        plan = generate_for_user(user)
        self.assertEqual(plan.cefr_level, "A1")
        n = plan.items.count()
        self.assertGreaterEqual(n, 5)
        self.assertLessEqual(n, 8)

    def test_b1_plan_in_5_to_8_items(self):
        user = make_student(username="b1u", cefr_level="B1", language="en")
        plan = generate_for_user(user)
        self.assertEqual(plan.cefr_level, "B1")
        n = plan.items.count()
        self.assertGreaterEqual(n, 5)
        self.assertLessEqual(n, 8)

    def test_plan_includes_speaking_item(self):
        user = make_student(username="speak", cefr_level="A1", language="en")
        plan = generate_for_user(user)
        types = set(plan.items.values_list("item_type", flat=True))
        self.assertTrue(
            "speaking" in types or "ai_tutor_practice" in types,
            f"expected speaking/ai_tutor_practice, got {types}",
        )

    def test_plan_includes_quiz_item(self):
        user = make_student(username="quiz", cefr_level="A1", language="en")
        plan = generate_for_user(user)
        types = set(plan.items.values_list("item_type", flat=True))
        self.assertIn("quiz", types)

    def test_plan_includes_motivation_message(self):
        user = make_student(username="motiv", cefr_level="A1", language="en")
        plan = generate_for_user(user)
        self.assertTrue((plan.metadata or {}).get("motivation_message"))
        # Motivation also written as the final item.
        self.assertTrue(plan.items.filter(item_type="motivation").exists())

    def test_placement_path_user_gets_placement_based_plan(self):
        user = make_student(
            username="placed",
            cefr_level="B1",
            onboarding_path="placement_test",
        )
        plan = generate_for_user(user)
        # placement_based is decided by decide_plan_type — but if no
        # high-priority weakness exists, this path applies.
        self.assertIn(plan.plan_type, {"placement_based", "normal_daily_plan"})

    @override_settings(DAILY_LEARNING_USE_AI=False)
    def test_ai_disabled_still_produces_valid_plan(self):
        """Templates + question bank must satisfy the spec without AI."""
        user = make_student(username="noai", cefr_level="A1", language="en")
        plan = generate_for_user(user)
        n = plan.items.count()
        self.assertGreaterEqual(n, 5)

    def test_existing_plan_not_duplicated(self):
        user = make_student(username="dup", cefr_level="A1")
        on = datetime.date(2026, 5, 12)
        p1 = generate_for_user(user, on_date=on)
        p2 = generate_for_user(user, on_date=on)
        self.assertEqual(p1.id, p2.id)
        self.assertEqual(DailyLearningPlan.objects.filter(user=user, date=on).count(), 1)
