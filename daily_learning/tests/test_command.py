"""Management command smoke tests."""
from __future__ import annotations

import datetime
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from daily_learning.models import DailyLearningPlan

from .factories import make_student


class GenerateCommandTests(TestCase):
    def test_command_generates_plan_for_user(self):
        user = make_student(username="cmdu", cefr_level="A1")
        out = StringIO()
        call_command(
            "generate_daily_learning_plans",
            "--user-id", str(user.id),
            "--no-ai",
            stdout=out,
        )
        self.assertTrue(
            DailyLearningPlan.objects.filter(user=user).exists()
        )
        self.assertIn("succeeded", out.getvalue())

    def test_dry_run_writes_nothing(self):
        user = make_student(username="dryu", cefr_level="A1")
        out = StringIO()
        call_command(
            "generate_daily_learning_plans",
            "--user-id", str(user.id),
            "--no-ai", "--dry-run",
            stdout=out,
        )
        self.assertFalse(DailyLearningPlan.objects.filter(user=user).exists())
        self.assertIn("DRY RUN", out.getvalue())

    def test_all_active_picks_onboarded_students(self):
        a = make_student(username="active1", cefr_level="A1",
                         onboarding_completed=True)
        b = make_student(username="active2", cefr_level="A1",
                         onboarding_completed=False)
        out = StringIO()
        call_command(
            "generate_daily_learning_plans",
            "--all-active", "--no-ai",
            stdout=out,
        )
        self.assertTrue(DailyLearningPlan.objects.filter(user=a).exists())
        self.assertFalse(DailyLearningPlan.objects.filter(user=b).exists())
