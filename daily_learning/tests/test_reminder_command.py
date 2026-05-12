"""Smoke tests for `send_daily_learning_reminders`.

Verifies that:
  1. The command runs cleanly with no users (graceful no-op).
  2. --dry-run prints intended recipients without sending.
  3. With a real plan, the right notification event type fires.

We don't assert email delivery — the notifications app already has
its own integration tests. These tests guard the command's wiring:
flag parsing, user selection, event-type routing.
"""
from __future__ import annotations

import datetime
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from daily_learning.services.daily_plan_generator import generate_for_user

from .factories import make_student


class SendDailyLearningRemindersTests(TestCase):
    def test_command_runs_with_no_active_users(self):
        """No users at all → graceful early exit, no exceptions."""
        out = StringIO()
        err = StringIO()
        call_command(
            "send_daily_learning_reminders",
            "--all-active",
            stdout=out, stderr=err,
        )
        # The command short-circuits with "No matching users." when the
        # active-student set is empty — we just want it to NOT raise.
        self.assertIn("No matching", out.getvalue())

    def test_dry_run_does_not_send(self):
        """With --dry-run, the command must report intended recipients
        without invoking the notifier."""
        user = make_student(username="rem_dry", cefr_level="A1")
        generate_for_user(user, on_date=timezone.localdate())
        out = StringIO()
        with mock.patch(
            "notifications.services.notification_service.NotificationService.trigger"
        ) as mock_trigger:
            call_command(
                "send_daily_learning_reminders",
                "--all-active", "--dry-run",
                stdout=out,
            )
        mock_trigger.assert_not_called()
        self.assertIn("[DRY]", out.getvalue())

    def test_command_fires_daily_plan_ready_for_active_streak(self):
        """A user with a fresh plan + no inactivity = DAILY_PLAN_READY."""
        user = make_student(username="rem_ready", cefr_level="A1")
        generate_for_user(user, on_date=timezone.localdate())
        out = StringIO()
        with mock.patch(
            "notifications.services.notification_service.NotificationService.trigger"
        ) as mock_trigger:
            call_command(
                "send_daily_learning_reminders",
                "--all-active",
                stdout=out,
            )
        self.assertTrue(mock_trigger.called)
        called_event = mock_trigger.call_args.args[0]
        from notifications import constants as Nc
        # Default path for an active student with a plan ready.
        self.assertEqual(called_event, Nc.DAILY_PLAN_READY)

    def test_command_fires_comeback_for_inactive_user(self):
        """A learner inactive for >=3 days should get the comeback
        reminder, not the default ready notification."""
        user = make_student(username="rem_inactive", cefr_level="A1")
        generate_for_user(user, on_date=timezone.localdate())
        out = StringIO()
        with mock.patch(
            "motivation.services.streak_service.get_inactive_days",
            return_value=5,
        ), mock.patch(
            "notifications.services.notification_service.NotificationService.trigger"
        ) as mock_trigger:
            call_command(
                "send_daily_learning_reminders",
                "--all-active",
                stdout=out,
            )
        self.assertTrue(mock_trigger.called)
        called_event = mock_trigger.call_args.args[0]
        from notifications import constants as Nc
        self.assertEqual(called_event, Nc.DAILY_PLAN_COMEBACK)

    def test_command_skips_users_without_a_plan(self):
        """Without a DailyLearningPlan for today, the reminder is
        skipped (it has nothing to point at)."""
        # User exists, no plan generated.
        make_student(username="rem_noplan", cefr_level="A1")
        out = StringIO()
        with mock.patch(
            "notifications.services.notification_service.NotificationService.trigger"
        ) as mock_trigger:
            call_command(
                "send_daily_learning_reminders",
                "--all-active",
                stdout=out,
            )
        mock_trigger.assert_not_called()
        self.assertIn("skipped", out.getvalue())
