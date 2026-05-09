"""Tests for the evaluator + `eval_local_model` command."""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from ai_engine import constants as AC
from ai_engine.services import providers as ai_providers
from ai_training import constants as C
from ai_training.models import AITrainingExample, DatasetBuild, EvaluationRun
from ai_training.services.evaluator import evaluate_build


def _seed_test_examples(build: DatasetBuild, n: int = 4):
    """Create N test-split AITrainingExample rows for the given build."""
    for i in range(n):
        AITrainingExample.objects.create(
            task_type=build.task_type,
            input={
                "question": f"Q-{i} What is the capital of France?",
                "student_answer": f"Paris-{i}",
                "correct_answer": "Paris",
            },
            output={
                "error_type": "tense" if i % 2 == 0 else "spelling",
                "explanation": "Sample explanation.",
            },
            cefr_level="B1", skill="grammar",
            quality_score=85, is_approved=True,
            content_hash=f"h-{build.id}-{i}", split=C.SPLIT_TEST,
            metadata={"build_id": build.id},
        )


@override_settings(AI_API_KEY="", AI_LOCAL_API_BASE="")
class EvaluatorTests(TestCase):
    def setUp(self):
        self.build = DatasetBuild.objects.create(
            name="eval-test", task_type=C.TASK_ERROR_ANALYSIS,
            status=C.BUILD_COMPLETED,
        )
        _seed_test_examples(self.build, n=4)

    def test_evaluate_records_run(self):
        # Patch the rules provider to always return "tense" — should
        # match 2/4 gold labels exactly.
        def stub(task_type, input_data, context):
            return {"output": {"error_type": "tense"},
                    "confidence": 0.95, "model_version": "stub"}
        with patch.dict(ai_providers.PROVIDERS,
                        {AC.P_RULES: stub}, clear=False):
            run = evaluate_build(self.build, name="eval-1")

        self.assertEqual(run.status, C.BUILD_COMPLETED)
        self.assertEqual(run.total_examples, 4)
        # Two gold labels are "tense" (i=0 and i=2).
        self.assertEqual(run.correct_count, 2)
        self.assertEqual(run.incorrect_count, 2)
        self.assertAlmostEqual(run.accuracy, 0.5)

    def test_evaluate_with_no_test_rows_fails_gracefully(self):
        # Different build with no test rows.
        empty_build = DatasetBuild.objects.create(
            name="empty-build", task_type=C.TASK_ERROR_ANALYSIS,
            status=C.BUILD_COMPLETED,
        )
        run = evaluate_build(empty_build, name="eval-empty")
        self.assertEqual(run.status, C.BUILD_FAILED)
        self.assertIn("No test examples", run.error_message)

    def test_forced_provider_locks_router(self):
        called = {"count": 0}
        def stub(task_type, input_data, context):
            called["count"] += 1
            return {"output": {"error_type": "tense"},
                    "confidence": 0.95, "model_version": "stub"}
        with patch.dict(ai_providers.PROVIDERS,
                        {AC.P_RULES: stub, AC.P_OPENAI: stub},
                        clear=False):
            run = evaluate_build(self.build, name="eval-forced",
                                 forced_provider=AC.P_OPENAI)
        # All 4 calls hit the (only-allowed) openai stub
        self.assertEqual(called["count"], 4)
        self.assertEqual(run.metadata["providers_used"].get(AC.P_OPENAI), 4)

    def test_command_runs_against_latest_completed_build(self):
        def stub(task_type, input_data, context):
            return {"output": {"error_type": "tense"},
                    "confidence": 0.95, "model_version": "stub"}
        with patch.dict(ai_providers.PROVIDERS,
                        {AC.P_RULES: stub}, clear=False):
            call_command(
                "eval_local_model",
                "--task-type", C.TASK_ERROR_ANALYSIS,
                "--name", "cmd-eval-1",
                stdout=StringIO(),
            )
        run = EvaluationRun.objects.get(name="cmd-eval-1")
        self.assertEqual(run.status, C.BUILD_COMPLETED)
        self.assertEqual(run.total_examples, 4)
