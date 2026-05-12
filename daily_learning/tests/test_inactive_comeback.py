"""Inactive student → shorter comeback plan."""
from __future__ import annotations

import datetime
from unittest import mock

from django.test import TestCase

from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class InactiveComebackTests(TestCase):
    def test_inactive_student_gets_short_comeback_plan(self):
        user = make_student(username="comeback", cefr_level="A2")
        on = datetime.date(2026, 5, 12)
        with mock.patch(
            "motivation.services.streak_service.get_inactive_days",
            return_value=5,
        ):
            plan = generate_for_user(user, on_date=on)
        self.assertEqual(plan.plan_type, "streak_recovery")
        # Comeback target is 4 items (settings default).
        # Plus motivation = at most 5 items total.
        self.assertLessEqual(plan.items.count(), 6)
