"""End-to-end tests covering the spec's required scenarios."""
import io
import json

from django.test import TestCase

from ai_training import constants as C
from ai_training.models import (
    AITrainingExample, DatasetBuild, DatasetQualityReport,
)
from ai_training.services import dispatch
from ai_training.services.dataset_exporter import assign_splits, export
from learning_core.models import AdaptiveExercise


def _make_exercise(*, question, answer, explanation, cefr="A1",
                   quality=85, reviewed=True, active=True):
    return AdaptiveExercise.objects.create(
        cefr_level=cefr, question_type="multiple_choice",
        question=question, correct_answer=answer,
        options=[answer, "wrong1", "wrong2", "wrong3"],
        explanation=explanation,
        difficulty_score=0.4,
        quality_score=quality,
        is_active=active, is_reviewed=reviewed,
    )


class ExerciseGenerationBuildTests(TestCase):
    """The most fully-sourced builder; we use it as the canonical
    end-to-end smoke for the spec scenarios."""

    def setUp(self):
        # 3 distinct, clean, high-quality items.
        for i in range(3):
            _make_exercise(
                question=f"She ___ home #{i}.",
                answer="goes",
                explanation=f"Explanation #{i}: third-person singular.",
            )
        # 1 low-quality item — must be filtered out at min-quality 80.
        _make_exercise(
            question="Low-q question, distinct.",
            answer="x", explanation="dummy", quality=40,
        )
        # 1 PII-tainted item — must be cleaned (not rejected) when
        # only the explanation contains an email.
        _make_exercise(
            question="PII-tainted question, distinct.",
            answer="ok",
            explanation="Email teacher at teacher@example.com if you need help.",
        )
        # 2 duplicates of an item — second one must be deduped.
        _make_exercise(
            question="Duplicate question content.",
            answer="dup", explanation="Same payload, twice.",
        )
        _make_exercise(
            question="Duplicate question content.",
            answer="dup", explanation="Same payload, twice.",
        )

    # 1. Dataset built from generated questions ----------------------

    def test_dataset_built_from_generated_questions(self):
        build = DatasetBuild.objects.create(
            name="eg_test_1", task_type=C.TASK_EXERCISE_GENERATION,
            filters={},
        )
        stats = dispatch.run(build, min_quality=60)
        self.assertEqual(build.status, C.BUILD_COMPLETED)
        self.assertGreater(stats["accepted"], 0)
        self.assertEqual(
            AITrainingExample.objects.filter(
                task_type=C.TASK_EXERCISE_GENERATION,
                metadata__build_id=build.id,
            ).count(),
            stats["accepted"],
        )

    # 2. Low-quality examples excluded -------------------------------

    def test_low_quality_examples_excluded(self):
        build = DatasetBuild.objects.create(
            name="eg_test_2", task_type=C.TASK_EXERCISE_GENERATION,
        )
        dispatch.run(build, min_quality=80)
        # The "Low-q" item (quality=40) must NOT appear.
        rows = AITrainingExample.objects.filter(metadata__build_id=build.id)
        for r in rows:
            self.assertGreaterEqual(r.quality_score, 80)
            self.assertNotIn("Low-q", r.input.get("topic", ""))

    # 3. Private data excluded / redacted ---------------------------

    def test_private_data_redacted_in_dataset(self):
        build = DatasetBuild.objects.create(
            name="eg_test_3", task_type=C.TASK_EXERCISE_GENERATION,
        )
        dispatch.run(build, min_quality=60)
        report = DatasetQualityReport.objects.get(build=build)
        self.assertGreaterEqual(report.private_data_filtered, 1)
        # No row in the dataset should still contain the email.
        for r in AITrainingExample.objects.filter(metadata__build_id=build.id):
            payload = json.dumps([r.input, r.output], ensure_ascii=False)
            self.assertNotIn("teacher@example.com", payload)

    # 4. JSONL export valid -----------------------------------------

    def test_jsonl_export_is_valid(self):
        build = DatasetBuild.objects.create(
            name="eg_test_4", task_type=C.TASK_EXERCISE_GENERATION,
        )
        dispatch.run(build, min_quality=60)
        assign_splits(build)

        sink = io.StringIO()
        job = export(build, fmt=C.FORMAT_JSONL, split=C.SPLIT_ALL, sink=sink)
        self.assertEqual(job.status, C.BUILD_COMPLETED)
        self.assertGreater(job.row_count, 0)

        sink.seek(0)
        rows = []
        for line in sink:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))   # raises on invalid JSON
        self.assertEqual(len(rows), job.row_count)
        for row in rows:
            self.assertIn("input",  row)
            self.assertIn("output", row)
            self.assertIn("task_type", row)

    def test_csv_export_round_trips(self):
        import csv as csvlib
        build = DatasetBuild.objects.create(
            name="eg_test_csv", task_type=C.TASK_EXERCISE_GENERATION,
        )
        dispatch.run(build, min_quality=60)
        assign_splits(build)
        sink = io.StringIO()
        job = export(build, fmt=C.FORMAT_CSV, split=C.SPLIT_ALL, sink=sink)
        self.assertEqual(job.status, C.BUILD_COMPLETED)
        sink.seek(0)
        reader = csvlib.DictReader(sink)
        rows = list(reader)
        self.assertEqual(len(rows), job.row_count)
        for r in rows:
            self.assertTrue(r["task_type"])
            json.loads(r["input"])    # column carries valid JSON
            json.loads(r["output"])

    # 5. Duplicate examples removed ---------------------------------

    def test_duplicates_removed(self):
        build = DatasetBuild.objects.create(
            name="eg_test_5", task_type=C.TASK_EXERCISE_GENERATION,
        )
        dispatch.run(build, min_quality=60)
        report = DatasetQualityReport.objects.get(build=build)
        # Setup created 2 duplicates; after dedup the row count must
        # be 1 less than the unique-content count.
        self.assertGreaterEqual(report.duplicates_removed, 1)
        # No two rows in the build share a content_hash.
        hashes = list(
            AITrainingExample.objects
            .filter(metadata__build_id=build.id)
            .values_list("content_hash", flat=True)
        )
        self.assertEqual(len(hashes), len(set(hashes)))


class SplitAssignmentTests(TestCase):
    def test_splits_are_deterministic(self):
        _make_exercise(
            question=f"Distinct question for split test.",
            answer="ok", explanation="An explanation that is sufficiently long.",
        )
        build = DatasetBuild.objects.create(
            name="splits_test", task_type=C.TASK_EXERCISE_GENERATION,
        )
        dispatch.run(build, min_quality=60)
        first  = assign_splits(build)
        second = assign_splits(build)
        self.assertEqual(first, second)


class TaskDispatchTests(TestCase):
    def test_unknown_task_type_fails_cleanly(self):
        build = DatasetBuild.objects.create(
            name="dispatch_test", task_type="error_analysis",  # valid enum
        )
        # Manually corrupt the task_type post-save to exercise the unknown branch.
        DatasetBuild.objects.filter(pk=build.pk).update(task_type="nope")
        build.refresh_from_db()
        stats = dispatch.run(build, min_quality=60)
        self.assertEqual(stats["accepted"], 0)
        self.assertIn("error", stats)
        build.refresh_from_db()
        self.assertEqual(build.status, C.BUILD_FAILED)
