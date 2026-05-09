import io
import json

from django.test import TestCase

from factory.models import TrainingDataset
from factory.services import dataset_builder
from learning_core.models import AdaptiveExercise


class DatasetBuilderTests(TestCase):
    def setUp(self):
        # Seed a tiny, deterministic question bank.
        for i in range(5):
            AdaptiveExercise.objects.create(
                cefr_level="A2", question_type="multiple_choice",
                question=f"Q{i}: She ___ home.",
                correct_answer="goes",
                options=["go", "goes", "going", "gone"],
                explanation=f"Explain {i}.",
                difficulty_score=0.4,
                quality_score=80,
                is_active=True, is_reviewed=True,
            )

    def _export_lines(self, ds: TrainingDataset) -> list[dict]:
        sink = io.StringIO()
        dataset_builder.export(ds, sink=sink)
        sink.seek(0)
        return [json.loads(line) for line in sink if line.strip()]

    def test_question_generation_dataset(self):
        ds = TrainingDataset.objects.create(
            name="qg", kind="question_generation",
            filters={"cefr_level": "A2"},
        )
        rows = self._export_lines(ds)
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertIn("prompt", r)
            self.assertIn("completion", r)

    def test_difficulty_estimation_dataset(self):
        ds = TrainingDataset.objects.create(
            name="diff", kind="difficulty_estimation",
            filters={"cefr_level": "A2"},
        )
        rows = self._export_lines(ds)
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertIn("text", r)
            self.assertIsInstance(r["label"], float)

    def test_cefr_classification_dataset(self):
        ds = TrainingDataset.objects.create(name="cefr", kind="cefr_classification")
        rows = self._export_lines(ds)
        self.assertEqual({r["label"] for r in rows}, {"A2"})

    def test_explanation_writing_dataset(self):
        ds = TrainingDataset.objects.create(name="expl", kind="explanation_writing")
        rows = self._export_lines(ds)
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertTrue(r["completion"])
            self.assertIn("Question:", r["prompt"])

    def test_rag_corpus_dataset(self):
        ds = TrainingDataset.objects.create(name="rag", kind="rag_corpus")
        rows = self._export_lines(ds)
        self.assertEqual(len(rows), 5)
        for r in rows:
            self.assertTrue(r["id"].startswith("qb:"))
            self.assertTrue(r["text"])
            self.assertEqual(r["metadata"]["cefr_level"], "A2")

    def test_export_creates_job_row(self):
        ds = TrainingDataset.objects.create(name="job-test", kind="cefr_classification")
        sink = io.StringIO()
        job = dataset_builder.export(ds, sink=sink)
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.row_count, 5)
        self.assertGreater(job.bytes_written, 0)
        self.assertEqual(ds.exports.count(), 1)

    def test_unknown_kind_fails_cleanly(self):
        ds = TrainingDataset.objects.create(name="bogus", kind="unknown_kind")
        sink = io.StringIO()
        job = dataset_builder.export(ds, sink=sink)
        self.assertEqual(job.status, "failed")
        self.assertIn("Unknown dataset kind", job.error_message)
