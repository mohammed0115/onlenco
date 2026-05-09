"""Tests for the model router.

We monkey-patch the provider registry directly (`providers.PROVIDERS`)
because that's what the real router consults at call time. This keeps
tests independent of any local LLM / OpenAI configuration on the
development machine.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_engine import constants as C
from ai_engine.models import ModelPredictionLog
from ai_engine.services import providers as _providers
from ai_engine.services.model_router import route_task

User = get_user_model()


def _stub_result(provider_label: str, confidence: float, output=None):
    """A provider that always returns the same shape — used by tests."""
    def _fn(task_type, input_data, context):
        return {
            "output": output or {"provider": provider_label, "ok": True},
            "confidence": confidence,
            "model_version": f"{provider_label}-test",
        }
    return _fn


def _none_provider(task_type, input_data, context):
    """A provider that always opts out (no result)."""
    return None


def _raising_provider(task_type, input_data, context):
    """A provider that always raises — used to exercise error logging."""
    raise RuntimeError("boom")


@override_settings(AI_LOCAL_API_BASE="", AI_API_KEY="")
class RouterRoutingTests(TestCase):
    """Each test patches the providers dict to set up the scenario it
    needs, then asserts the router's response + the audit log."""

    # 1. Local route ----------------------------------------------------

    def test_local_route_uses_local_llm_when_above_threshold(self):
        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES:            _none_provider,
            C.P_LOCAL_CLASSIFIER: _none_provider,
            C.P_LOCAL_LLM:        _stub_result(C.P_LOCAL_LLM, 0.85),
            C.P_OPENAI:           _stub_result(C.P_OPENAI, 0.95),
        }, clear=False):
            result = route_task(
                C.TASK_ERROR_ANALYSIS,
                {"student_answer": "ate", "correct_answer": "eaten"},
            )
        self.assertEqual(result["provider"], C.P_LOCAL_LLM)
        self.assertTrue(result["fallback_used"])  # rules + classifier skipped
        self.assertGreaterEqual(result["confidence"], 0.7)
        # One success log (the winning provider) — no logs for the two skips.
        log = ModelPredictionLog.objects.get(success=True)
        self.assertEqual(log.provider, C.P_LOCAL_LLM)
        self.assertTrue(log.fallback_used)

    # 2. RAG route ------------------------------------------------------

    def test_rag_route_serves_exercise_generation(self):
        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES:     _none_provider,
            C.P_RAG:       _stub_result(C.P_RAG, 0.88, output={
                "question": "She ___ home.", "options": ["go", "goes"],
                "correct_answer": "goes", "explanation": "3rd-singular adds -s.",
            }),
            C.P_LOCAL_LLM: _stub_result(C.P_LOCAL_LLM, 0.95),
            C.P_OPENAI:    _stub_result(C.P_OPENAI, 0.95),
        }, clear=False):
            result = route_task(
                C.TASK_EXERCISE_GENERATION,
                {"cefr_level": "A1", "skill": "grammar"},
            )
        self.assertEqual(result["provider"], C.P_RAG)
        self.assertEqual(result["output"]["correct_answer"], "goes")
        log = ModelPredictionLog.objects.get(success=True)
        self.assertEqual(log.provider, C.P_RAG)

    # 3. OpenAI fallback ------------------------------------------------

    def test_openai_fallback_when_others_unavailable(self):
        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES:            _none_provider,
            C.P_LOCAL_CLASSIFIER: _none_provider,
            C.P_LOCAL_LLM:        _none_provider,
            C.P_RAG:              _none_provider,
            C.P_OPENAI:           _stub_result(C.P_OPENAI, 0.85),
        }, clear=False):
            result = route_task(
                C.TASK_ERROR_ANALYSIS,
                {"student_answer": "ate", "correct_answer": "eaten",
                 "question": "She has ___ lunch."},
            )
        self.assertEqual(result["provider"], C.P_OPENAI)
        self.assertTrue(result["fallback_used"])
        # One success log + the upstream skips were silent (no log).
        success_logs = ModelPredictionLog.objects.filter(success=True)
        self.assertEqual(success_logs.count(), 1)
        self.assertEqual(success_logs.get().provider, C.P_OPENAI)

    # 4. Low-confidence fallback ---------------------------------------

    def test_low_confidence_falls_through_to_next_provider(self):
        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES:            _stub_result(C.P_RULES, 0.4),       # < 0.9
            C.P_LOCAL_CLASSIFIER: _stub_result(C.P_LOCAL_CLASSIFIER, 0.5),  # < 0.85
            C.P_LOCAL_LLM:        _stub_result(C.P_LOCAL_LLM, 0.9),   # >= 0.7 ✓
            C.P_OPENAI:           _stub_result(C.P_OPENAI, 0.95),
        }, clear=False):
            result = route_task(
                C.TASK_ERROR_ANALYSIS,
                {"student_answer": "ate", "correct_answer": "eaten"},
            )
        self.assertEqual(result["provider"], C.P_LOCAL_LLM)
        self.assertTrue(result["fallback_used"])
        # Each below-threshold attempt is recorded as success=False so
        # the operator can see *how often* providers misfire.
        below = ModelPredictionLog.objects.filter(success=False)
        self.assertEqual(below.count(), 2)
        self.assertSetEqual(
            set(below.values_list("provider", flat=True)),
            {C.P_RULES, C.P_LOCAL_CLASSIFIER},
        )
        for row in below:
            self.assertTrue(row.reason.startswith("below_threshold:"))

    # 5. Error logging --------------------------------------------------

    def test_provider_exception_logged_then_router_continues(self):
        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES:            _none_provider,
            C.P_LOCAL_CLASSIFIER: _raising_provider,
            C.P_LOCAL_LLM:        _stub_result(C.P_LOCAL_LLM, 0.9),
            C.P_OPENAI:           _stub_result(C.P_OPENAI, 0.95),
        }, clear=False):
            result = route_task(
                C.TASK_ERROR_ANALYSIS,
                {"student_answer": "ate", "correct_answer": "eaten"},
            )
        # Router didn't crash — it continued past the raising provider.
        self.assertEqual(result["provider"], C.P_LOCAL_LLM)
        # One failure log for the raising provider, one success for local_llm.
        fail_log = ModelPredictionLog.objects.get(success=False)
        self.assertEqual(fail_log.provider, C.P_LOCAL_CLASSIFIER)
        self.assertIn("RuntimeError", fail_log.error_message)
        self.assertEqual(fail_log.reason, "provider_exception")
        self.assertTrue(fail_log.fallback_used)

    # 6. All-failed terminal log ---------------------------------------

    def test_all_providers_fail_returns_none_and_logs_terminal(self):
        with patch.dict(_providers.PROVIDERS, {
            p: _none_provider for p in C.PIPELINES[C.TASK_ERROR_ANALYSIS]
        }, clear=False):
            result = route_task(
                C.TASK_ERROR_ANALYSIS,
                {"student_answer": "x", "correct_answer": "y"},
            )
        self.assertEqual(result["provider"], C.P_NONE)
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["reason"], "all_providers_failed")
        terminal = ModelPredictionLog.objects.filter(provider=C.P_NONE).first()
        self.assertIsNotNone(terminal)
        self.assertFalse(terminal.success)

    # 7. Unknown task type ---------------------------------------------

    def test_unknown_task_returns_none_and_logs(self):
        result = route_task("not_a_real_task", {})
        self.assertEqual(result["provider"], C.P_NONE)
        self.assertTrue(result["reason"].startswith("unknown_task_type:"))
        self.assertTrue(
            ModelPredictionLog.objects.filter(provider=C.P_NONE).exists()
        )

    # 8. User attribution ----------------------------------------------

    def test_authenticated_user_recorded_on_log(self):
        u = User.objects.create_user(username="r@x.com", email="r@x.com",
                                     password="pw")
        with patch.dict(_providers.PROVIDERS, {
            C.P_RULES:  _stub_result(C.P_RULES, 0.95),
        }, clear=False):
            route_task(C.TASK_ERROR_ANALYSIS,
                       {"student_answer": "x", "correct_answer": "x"},
                       user=u)
        log = ModelPredictionLog.objects.get(provider=C.P_RULES)
        self.assertEqual(log.user_id, u.id)


@override_settings(AI_LOCAL_API_BASE="", AI_API_KEY="")
class RouterIntegrationTests(TestCase):
    """Light-touch tests against the *real* providers — no mocking — to
    confirm the rules path actually does something useful out of the
    box without external services."""

    def test_rules_handles_empty_answer_for_error_analysis(self):
        result = route_task(
            C.TASK_ERROR_ANALYSIS,
            {"student_answer": "", "correct_answer": "London",
             "question": "Capital of UK?"},
        )
        self.assertEqual(result["provider"], C.P_RULES)
        self.assertEqual(result["output"]["error_type"], "missing_answer")

    def test_rules_handles_match_for_error_analysis(self):
        result = route_task(
            C.TASK_ERROR_ANALYSIS,
            {"student_answer": "London", "correct_answer": "London"},
        )
        self.assertEqual(result["provider"], C.P_RULES)
        self.assertEqual(result["output"]["error_type"], "none")

    def test_rules_short_text_for_cefr_prediction(self):
        result = route_task(C.TASK_CEFR_PREDICTION, {"text": "Hi there"})
        self.assertEqual(result["provider"], C.P_RULES)
        self.assertEqual(result["output"]["cefr_level"], "A0")

    def test_rules_short_writing_feedback(self):
        result = route_task(C.TASK_WRITING_FEEDBACK, {"text": "ok"})
        self.assertEqual(result["provider"], C.P_RULES)
        self.assertIn("complete sentence", result["output"]["feedback"].lower())
