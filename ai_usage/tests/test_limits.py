from decimal import Decimal

from django.test import TestCase

from ai_usage.services import limit_service
from subscriptions.models import FreeTrialUsage
from subscriptions.services import quota_service

from .helpers import give_plan, make_user


class DailyLimitTests(TestCase):
    def test_base_plan_gives_5_minutes_per_day(self):
        u = make_user("base")
        give_plan(u, 5)
        self.assertEqual(limit_service.get_allowed_minutes_for_student(u), Decimal("5.00"))

    def test_upgrade_10_plan_gives_10_minutes(self):
        u = make_user("u10")
        give_plan(u, 10)
        self.assertEqual(limit_service.get_allowed_minutes_for_student(u), Decimal("10.00"))

    def test_upgrade_20_plan_gives_20_minutes(self):
        u = make_user("u20")
        give_plan(u, 20)
        self.assertEqual(limit_service.get_allowed_minutes_for_student(u), Decimal("20.00"))

    def test_upgrade_30_plan_gives_30_minutes(self):
        u = make_user("u30")
        give_plan(u, 30)
        self.assertEqual(limit_service.get_allowed_minutes_for_student(u), Decimal("30.00"))

    def test_free_first_day_gives_5_minutes_only_once(self):
        u = make_user("trial")
        # No subscription → one-shot 5-minute trial granted on first read.
        self.assertEqual(limit_service.get_allowed_minutes_for_student(u), Decimal("5.00"))
        row = limit_service.create_or_update_daily_limit(u)
        self.assertTrue(row.is_free_first_day)
        trial = FreeTrialUsage.objects.get(user=u)
        self.assertEqual(trial.free_seconds_granted, 5 * 60)
        # Consume it entirely, then a re-grant must NOT happen (one-shot).
        quota_service.consume_free_trial_seconds(u, 300)
        limit_service.create_or_update_daily_limit(u)
        trial.refresh_from_db()
        self.assertEqual(trial.free_seconds_granted, 5 * 60)
        self.assertTrue(trial.is_consumed)

    def test_student_cannot_start_ai_tutor_when_minutes_finished(self):
        # Pure free-trial student (no subscription): drain the one-shot trial
        # so NOTHING is left in any bucket — the true "finished" state.
        u = make_user("done")
        quota_service.get_or_create_free_trial(u)
        quota_service.consume_free_trial_seconds(u, 300)
        allowed, info = limit_service.check_can_start_ai_tutor(u)
        self.assertFalse(allowed)
        self.assertEqual(info["reason"], "daily_minutes_exhausted")
        self.assertIn("المعلم الذكي", info["message"]["ar"])
        self.assertIn("AI Tutor", info["message"]["en"])

    def test_student_can_start_with_minutes(self):
        u = make_user("ok")
        give_plan(u, 10)
        allowed, _info = limit_service.check_can_start_ai_tutor(u)
        self.assertTrue(allowed)

    def test_actual_session_duration_updates_used_minutes(self):
        u = make_user("dur")
        give_plan(u, 5)
        row = limit_service.finalize_ai_tutor_minutes(u, 2)
        self.assertEqual(row.used_minutes, Decimal("2.00"))
        self.assertEqual(row.remaining_minutes, Decimal("3.00"))

    def test_remaining_minutes_never_negative_display(self):
        u = make_user("neg")
        give_plan(u, 5)
        row = limit_service.finalize_ai_tutor_minutes(u, 99)  # overspend
        self.assertGreaterEqual(row.remaining_minutes, Decimal("0.00"))
        self.assertEqual(row.remaining_minutes, Decimal("0.00"))
        self.assertTrue(row.is_exceeded)
