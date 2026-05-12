"""Model-layer invariants."""
from __future__ import annotations

import datetime

from django.db import IntegrityError
from django.test import TestCase

from daily_learning.models import (
    DailyGoal,
    DailyLearningItem,
    DailyLearningPlan,
    DailyLearningResult,
)

from .factories import make_student


class ModelInvariantTests(TestCase):
    def test_unique_plan_per_user_date(self):
        user = make_student(username="uniqu", cefr_level="A1")
        DailyLearningPlan.objects.create(
            user=user, date=datetime.date(2026, 5, 12),
            plan_type="normal_daily_plan",
        )
        with self.assertRaises(IntegrityError):
            DailyLearningPlan.objects.create(
                user=user, date=datetime.date(2026, 5, 12),
                plan_type="normal_daily_plan",
            )

    def test_unique_goal_per_user_date_type(self):
        user = make_student(username="ugoal", cefr_level="A1")
        DailyGoal.objects.create(
            user=user, date=datetime.date(2026, 5, 12),
            goal_type="answer_questions", target_value=5,
        )
        with self.assertRaises(IntegrityError):
            DailyGoal.objects.create(
                user=user, date=datetime.date(2026, 5, 12),
                goal_type="answer_questions", target_value=10,
            )

    def test_progress_percent_zero_when_no_items(self):
        user = make_student(username="prog0", cefr_level="A1")
        plan = DailyLearningPlan.objects.create(
            user=user, date=datetime.date(2026, 5, 12),
        )
        self.assertEqual(plan.progress_percent, 0)

    def test_progress_percent_after_completions(self):
        user = make_student(username="progN", cefr_level="A1")
        plan = DailyLearningPlan.objects.create(
            user=user, date=datetime.date(2026, 5, 12),
        )
        for i in range(4):
            DailyLearningItem.objects.create(
                daily_plan=plan, item_type="quiz",
                order=i, is_completed=(i < 2),
            )
        self.assertEqual(plan.progress_percent, 50)

    def test_result_one_per_plan(self):
        user = make_student(username="resu", cefr_level="A1")
        plan = DailyLearningPlan.objects.create(
            user=user, date=datetime.date(2026, 5, 12),
        )
        DailyLearningResult.objects.create(user=user, daily_plan=plan)
        # OneToOne — second create should fail
        with self.assertRaises(IntegrityError):
            DailyLearningResult.objects.create(user=user, daily_plan=plan)
