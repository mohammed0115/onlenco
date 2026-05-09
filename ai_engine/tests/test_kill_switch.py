"""Tests for `ProviderKillSwitch` + `check_provider_health`."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from ai_engine import constants as C
from ai_engine.models import ModelPredictionLog, ProviderKillSwitch
from ai_engine.services import providers as _providers
from ai_engine.services.model_router import route_task


def _stub(label: str, confidence: float = 0.95):
    def fn(task_type, input_data, context):
        return {"output": {"served_by": label},
                "confidence": confidence,
                "model_version": f"{label}-test"}
    return fn


@override_settings(AI_API_KEY="", AI_LOCAL_API_BASE="")
class KillSwitchTests(TestCase):
    def test_disabled_provider_is_skipped(self):
        # Disable the rules provider for error_analysis.
        ProviderKillSwitch.objects.create(
            task_type=C.TASK_ERROR_ANALYSIS, provider=C.P_RULES,
            disabled=True, reason="testing",
        )

        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES:            _stub("rules"),
            C.P_LOCAL_CLASSIFIER: _stub("local_classifier"),
            C.P_LOCAL_LLM:        _stub("local_llm"),
            C.P_OPENAI:           _stub("openai"),
        }, clear=False):
            result = route_task(
                C.TASK_ERROR_ANALYSIS,
                {"student_answer": "x", "correct_answer": "y"},
            )
        self.assertNotEqual(result["provider"], C.P_RULES)
        # Kill-switch row produced exactly one log entry tagged kill_switch
        kills = ModelPredictionLog.objects.filter(
            provider=C.P_RULES, reason__startswith="kill_switch:",
        )
        self.assertEqual(kills.count(), 1)

    def test_wildcard_disables_provider_for_all_tasks(self):
        ProviderKillSwitch.objects.create(
            task_type="*", provider=C.P_OPENAI,
            disabled=True, reason="cost cap",
        )
        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES: lambda *a, **kw: None,    # all earlier providers skip
            C.P_LOCAL_CLASSIFIER: lambda *a, **kw: None,
            C.P_LOCAL_LLM: lambda *a, **kw: None,
            C.P_OPENAI: _stub("openai"),
        }, clear=False):
            result = route_task(
                C.TASK_ERROR_ANALYSIS,
                {"student_answer": "x", "correct_answer": "y"},
            )
        # Wildcard kill-switch wins — OpenAI never serves.
        self.assertEqual(result["provider"], C.P_NONE)

    def test_expired_kill_switch_is_ignored(self):
        # Already-expired switch must not block routing.
        ProviderKillSwitch.objects.create(
            task_type=C.TASK_ERROR_ANALYSIS, provider=C.P_RULES,
            disabled=True, reason="old incident",
            expires_at=timezone.now() - timedelta(hours=1),
        )
        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES: _stub("rules"),
        }, clear=False):
            result = route_task(
                C.TASK_ERROR_ANALYSIS,
                {"student_answer": "x", "correct_answer": "y"},
            )
        self.assertEqual(result["provider"], C.P_RULES)


@override_settings(AI_API_KEY="", AI_LOCAL_API_BASE="")
class HealthCheckCommandTests(TestCase):
    def setUp(self):
        # Seed a window of logs: rules with 90% success, openai with 50%.
        for _ in range(9):
            ModelPredictionLog.objects.create(
                task_type=C.TASK_ERROR_ANALYSIS, provider=C.P_RULES,
                confidence=0.95, success=True,
            )
        ModelPredictionLog.objects.create(
            task_type=C.TASK_ERROR_ANALYSIS, provider=C.P_RULES,
            confidence=0.10, success=False,
        )
        for _ in range(5):
            ModelPredictionLog.objects.create(
                task_type=C.TASK_ERROR_ANALYSIS, provider=C.P_OPENAI,
                confidence=0.95, success=True,
            )
        for _ in range(5):
            ModelPredictionLog.objects.create(
                task_type=C.TASK_ERROR_ANALYSIS, provider=C.P_OPENAI,
                confidence=0.20, success=False,
            )

    def test_flags_low_success_rate(self):
        out = StringIO()
        with self.assertRaises(SystemExit) as cm:
            call_command(
                "check_provider_health",
                "--days", "1", "--min-success-rate", "0.80",
                "--min-samples", "5", stdout=out,
            )
        # Non-zero exit when anything is flagged.
        self.assertNotEqual(cm.exception.code, 0)
        text = out.getvalue()
        self.assertIn("openai", text)
        self.assertIn("FLAGGED", text)
        self.assertIn("rules", text)

    def test_auto_disable_creates_kill_switch_rows(self):
        with self.assertRaises(SystemExit):
            call_command(
                "check_provider_health",
                "--days", "1", "--min-success-rate", "0.80",
                "--min-samples", "5", "--auto-disable",
                stdout=StringIO(),
            )
        # OpenAI was below threshold → kill switch row exists.
        self.assertTrue(
            ProviderKillSwitch.objects.filter(
                provider=C.P_OPENAI, disabled=True,
            ).exists()
        )

    def test_clean_window_does_not_flag_or_exit(self):
        ModelPredictionLog.objects.all().delete()
        for _ in range(20):
            ModelPredictionLog.objects.create(
                task_type=C.TASK_ERROR_ANALYSIS, provider=C.P_RULES,
                confidence=0.95, success=True,
            )
        # Healthy → command exits 0 (call_command does not raise).
        call_command(
            "check_provider_health", "--days", "1",
            "--min-samples", "5", stdout=StringIO(),
        )
