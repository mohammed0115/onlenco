"""12A.1 meta tests: docs updated, dashboard/API reflect migrated features."""
import os

from django.conf import settings
from django.test import TestCase
from rest_framework.test import APIClient

from ai_usage import constants as C
from ai_usage.services import usage_logger

from .helpers import give_plan, make_user


def _read(rel):
    return open(os.path.join(settings.BASE_DIR, rel), encoding="utf-8").read()


class DocsUpdatedTests(TestCase):
    def test_ai_calls_audit_report_updated(self):
        self.assertIn("Prompt 12A.1 Re-Audit", _read("docs/AI_CALLS_AUDIT_REPORT.md"))

    def test_wrapper_migration_report_updated(self):
        text = _read("docs/AI_WRAPPER_MIGRATION_REPORT.md")
        self.assertIn("Prompt 12A.1", text)
        self.assertIn("Plan Minutes Mismatch", text)
        self.assertIn("Legacy AI Usage Logger Retirement Plan", text)


def _admin():
    # role="admin" satisfies both the API role check and platform_admin's
    # is_control_user gate used by the dashboard.
    return make_user("metaadmin", role="admin")


class DashboardApiFeatureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Log rows across migrated features.
        for feat in (C.FEATURE_CHALLENGE_EXPLANATION, C.FEATURE_AI_TUTOR,
                     C.FEATURE_CONTENT_GENERATION, C.FEATURE_TTS):
            usage_logger.log_success(feature=feat, model_name="gpt-4o-mini",
                                     input_tokens=10, output_tokens=5)

    def test_ai_usage_api_groups_by_feature(self):
        self.client.force_authenticate(_admin())
        resp = self.client.get("/api/ai-usage/features/")
        self.assertEqual(resp.status_code, 200)
        features = {row["feature"] for row in resp.data}
        self.assertIn(C.FEATURE_CHALLENGE_EXPLANATION, features)
        self.assertIn(C.FEATURE_TTS, features)
        self.assertIn(C.FEATURE_CONTENT_GENERATION, features)

    def test_ai_usage_dashboard_shows_migrated_features(self):
        # The dashboard is a session-auth Django view (not DRF) — use the
        # Django test client with force_login.
        from django.test import Client
        dclient = Client(SERVER_NAME="127.0.0.1")
        dclient.force_login(_admin())
        resp = dclient.get("/control/ai-usage/")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn(C.FEATURE_CHALLENGE_EXPLANATION, body)

    def test_student_limits_api_still_works(self):
        student = make_user("metastud")
        give_plan(student, 10)
        self.client.force_authenticate(student)
        resp = self.client.get("/api/ai-usage/limits/me/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(str(resp.data["allowed_minutes"]), "10.00")
