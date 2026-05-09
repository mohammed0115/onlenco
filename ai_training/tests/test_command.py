"""Smoke tests for the management commands."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from ai_training import constants as C
from ai_training.models import (
    AITrainingExample, DatasetBuild, DatasetQualityReport,
)
from learning_core.models import AdaptiveExercise


class BuildCommandTests(TestCase):
    def setUp(self):
        for i in range(3):
            AdaptiveExercise.objects.create(
                cefr_level="B1", question_type="multiple_choice",
                question=f"Question #{i} content.",
                correct_answer="ok",
                options=["ok", "a", "b", "c"],
                explanation=f"Explanation #{i}.",
                difficulty_score=0.5, quality_score=85,
                is_active=True, is_reviewed=True,
            )

    def test_build_command_runs_and_assigns_splits(self):
        out = StringIO()
        call_command(
            "build_training_dataset",
            "--name", "cmd_test",
            "--task-type", C.TASK_EXERCISE_GENERATION,
            "--min-quality", "60",
            stdout=out,
        )
        build = DatasetBuild.objects.get(name="cmd_test")
        self.assertEqual(build.status, C.BUILD_COMPLETED)
        self.assertGreater(build.example_count, 0)
        # Splits should have been assigned post-build.
        rows = AITrainingExample.objects.filter(metadata__build_id=build.id)
        for r in rows:
            self.assertIn(r.split, [C.SPLIT_TRAIN, C.SPLIT_VALIDATION, C.SPLIT_TEST])

    def test_report_command_outputs_stats(self):
        call_command(
            "build_training_dataset", "--name", "report_test",
            "--task-type", C.TASK_EXERCISE_GENERATION, "--min-quality", "60",
            stdout=StringIO(),
        )
        out = StringIO()
        call_command("generate_dataset_report", "--build", "report_test", stdout=out)
        text = out.getvalue()
        self.assertIn("report_test", text)
        self.assertIn("examples", text)
        self.assertIn("by CEFR", text)


class ExportCommandTests(TestCase):
    def setUp(self):
        for i in range(3):
            AdaptiveExercise.objects.create(
                cefr_level="A2", question_type="multiple_choice",
                question=f"Export Q #{i}.",
                correct_answer="ok",
                options=["ok", "a", "b", "c"],
                explanation=f"Export Expl #{i}.",
                difficulty_score=0.4, quality_score=85,
                is_active=True, is_reviewed=True,
            )
        call_command(
            "build_training_dataset", "--name", "exp_build",
            "--task-type", C.TASK_EXERCISE_GENERATION, "--min-quality", "60",
            stdout=StringIO(),
        )

    def test_export_jsonl_via_command(self):
        out = StringIO()
        call_command(
            "export_training_dataset",
            "--build", "exp_build",
            "--format", C.FORMAT_JSONL,
            "--split", C.SPLIT_ALL,
            stdout=out,
        )
        text = out.getvalue()
        self.assertIn("status=completed", text)
        self.assertIn("rows=", text)

    def test_export_falls_back_to_latest_for_task_type(self):
        out = StringIO()
        call_command(
            "export_training_dataset",
            "--task-type", C.TASK_EXERCISE_GENERATION,
            "--format", C.FORMAT_JSONL,
            stdout=out,
        )
        self.assertIn("status=completed", out.getvalue())
