from django.test import TestCase

from exams import constants as C
from exams.models import QuestionGenerationBatch
from exams.services.bulk_generation_service import (
    generate_chunk,
    generate_to_target,
)
from learning_core.models import AdaptiveExercise


class BulkGenerationTests(TestCase):
    def test_dry_run_writes_nothing(self):
        before = AdaptiveExercise.objects.count()
        stats = generate_chunk(
            cefr_level="A1", chunk_size=20, dry_run=True, seed=1,
        )
        self.assertEqual(AdaptiveExercise.objects.count(), before)
        self.assertEqual(stats["written"], 0)
        self.assertGreater(stats["candidates"], 0)

    def test_small_run_writes_items(self):
        stats = generate_chunk(cefr_level="A1", chunk_size=15, seed=2)
        self.assertGreaterEqual(stats["written"], 1)
        self.assertGreaterEqual(
            AdaptiveExercise.objects.filter(cefr_level="A1").count(), 1
        )

    def test_resume_uses_existing_batch(self):
        b1 = generate_to_target(target_count=5, cefr_level="A1", chunk_size=5)
        self.assertEqual(b1.status, C.BATCH_COMPLETED)
        b2 = generate_to_target(
            target_count=10, cefr_level="A1", chunk_size=5, resume=True,
        )
        # If resume picked up the failed/paused/running batch, we'd
        # update it; completed batches don't qualify for resume so a new
        # one is started — both behaviors are valid, but we should never
        # have generated < 5 items total.
        self.assertGreaterEqual(
            AdaptiveExercise.objects.filter(cefr_level="A1").count(), 5
        )
        self.assertIsNotNone(b2.batch_id)

    def test_idempotent_no_duplicate_codes(self):
        generate_to_target(target_count=20, cefr_level="A1", chunk_size=20)
        generate_to_target(target_count=20, cefr_level="A1", chunk_size=20)
        # codes are unique because of the partial unique constraint
        codes = list(AdaptiveExercise.objects.exclude(code="").values_list("code", flat=True))
        self.assertEqual(len(codes), len(set(codes)))
