"""Item completion + plan finalization."""
from __future__ import annotations

from django.test import TestCase

from daily_learning.models import DailyLearningResult
from daily_learning.services.daily_plan_generator import generate_for_user
from daily_learning.services.daily_progress_service import (
    complete_plan,
    mark_item_complete,
)

from .factories import make_student


class ProgressTests(TestCase):
    def test_can_complete_single_item(self):
        user = make_student(username="prog1", cefr_level="A1")
        plan = generate_for_user(user)
        item = plan.items.exclude(item_type="motivation").first()
        self.assertFalse(item.is_completed)
        mark_item_complete(item, user_answer="my answer")
        item.refresh_from_db()
        self.assertTrue(item.is_completed)

    def test_complete_plan_writes_result_row(self):
        user = make_student(username="prog2", cefr_level="A1")
        plan = generate_for_user(user)
        # Mark all items complete first
        for it in plan.items.all():
            mark_item_complete(it)
        result = complete_plan(plan, force=False)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, DailyLearningResult)
        self.assertGreater(result.completed_items_count, 0)
        self.assertEqual(result.total_items_count, plan.items.count())

    def test_force_complete_with_partial_progress(self):
        user = make_student(username="prog3", cefr_level="A1")
        plan = generate_for_user(user)
        first = plan.items.order_by("order").first()
        mark_item_complete(first)
        result = complete_plan(plan, force=True)
        self.assertTrue(result.streak_updated)
        # Result counts reflect partial state.
        self.assertEqual(result.completed_items_count, 1)

    def test_completing_item_rolls_plan_to_in_progress(self):
        user = make_student(username="prog4", cefr_level="A1")
        plan = generate_for_user(user)
        self.assertEqual(plan.status, "pending")
        first = plan.items.order_by("order").first()
        mark_item_complete(first)
        plan.refresh_from_db()
        self.assertEqual(plan.status, "in_progress")
