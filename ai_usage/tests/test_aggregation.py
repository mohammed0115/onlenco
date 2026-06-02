from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from ai_usage import constants as C
from ai_usage.models import AIDailyUsageSummary
from ai_usage.services import aggregation, usage_logger

from .helpers import give_plan, make_user


class AggregationTests(TestCase):
    def setUp(self):
        self.u = make_user("agg")
        self.today = timezone.localdate()
        usage_logger.log_success(user=self.u, feature=C.FEATURE_AI_TUTOR,
                                 model_name="gpt-4o-mini", input_tokens=100,
                                 output_tokens=50, ai_minutes_used=Decimal("2"))
        usage_logger.log_success(user=self.u, feature=C.FEATURE_LIBRARY,
                                 model_name="gpt-4o-mini", input_tokens=200, output_tokens=10)
        usage_logger.log_failure(user=self.u, feature=C.FEATURE_LIBRARY,
                                 model_name="gpt-4o-mini", error_message="x")

    def test_aggregate_ai_usage_daily(self):
        written = aggregation.aggregate_day(self.today)
        self.assertEqual(written, 1)
        s = AIDailyUsageSummary.objects.get(date=self.today, user=self.u)
        self.assertEqual(s.total_requests, 3)
        self.assertEqual(s.successful_requests, 2)
        self.assertEqual(s.failed_requests, 1)
        self.assertEqual(s.total_tokens, 360)
        self.assertEqual(s.ai_tutor_minutes_used, Decimal("2.00"))

    def test_summary_counts_failed_requests(self):
        aggregation.aggregate_day(self.today)
        s = AIDailyUsageSummary.objects.get(date=self.today, user=self.u)
        self.assertEqual(s.failed_requests, 1)

    def test_summary_groups_by_feature_and_model(self):
        aggregation.aggregate_day(self.today)
        s = AIDailyUsageSummary.objects.get(date=self.today, user=self.u)
        self.assertIn("name", s.top_feature)
        self.assertEqual(s.top_model.get("name"), "gpt-4o-mini")

    def test_recalculate_daily_summary(self):
        aggregation.aggregate_day(self.today)
        # add another row, recalc must reflect it (and not duplicate the summary)
        usage_logger.log_success(user=self.u, feature="other", model_name="gpt-4o-mini",
                                 input_tokens=5, output_tokens=5)
        aggregation.recalculate_day(self.today)
        self.assertEqual(AIDailyUsageSummary.objects.filter(date=self.today, user=self.u).count(), 1)
        s = AIDailyUsageSummary.objects.get(date=self.today, user=self.u)
        self.assertEqual(s.total_requests, 4)

    def test_aggregate_command_idempotent(self):
        call_command("aggregate_ai_usage_daily", f"--date={self.today}", stdout=StringIO())
        call_command("aggregate_ai_usage_daily", f"--date={self.today}", stdout=StringIO())
        self.assertEqual(AIDailyUsageSummary.objects.filter(date=self.today).count(), 1)


class CommandTests(TestCase):
    def test_update_student_daily_limits_command(self):
        u = make_user("limcmd")
        give_plan(u, 10)
        out = StringIO()
        call_command("update_student_daily_limits", f"--user={u.id}", stdout=out)
        from ai_usage.models import StudentDailyAILimit
        row = StudentDailyAILimit.objects.get(student=u)
        self.assertEqual(row.allowed_minutes, Decimal("10.00"))

    @override_settings(AI_USAGE_DAILY_BUDGET_USD="0.0001", AI_USAGE_ALERT_EMAILS=[])
    def test_ai_usage_alerts_threshold(self):
        u = make_user("spender")
        usage_logger.log_success(user=u, feature="other", model_name="gpt-4o-mini",
                                 input_tokens=1_000_000, output_tokens=1_000_000)
        from ai_usage.services import alert_service
        alerts = alert_service.evaluate_alerts()
        types = {a["type"] for a in alerts}
        self.assertIn("daily_budget_exceeded", types)
