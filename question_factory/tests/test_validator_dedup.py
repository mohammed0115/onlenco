from django.test import TestCase

from question_factory.models import GeneratedQuestion
from question_factory.services import duplicate_detector, question_validator


def _good_item(**overrides):
    item = {
        "question_text": "She ___ to school every day.",
        "correct_answer": "goes",
        "options": ["go", "goes", "going", "gone"],
        "question_type": "multiple_choice",
        "difficulty_score": 0.3,
        "cefr_level": "A1",
        "language": "en",
    }
    item.update(overrides)
    return item


class QuestionValidatorTests(TestCase):
    def test_clean_item_passes(self):
        score, fails = question_validator.evaluate(_good_item())
        self.assertEqual(fails, [])
        self.assertEqual(score, 100)
        self.assertTrue(question_validator.passes(_good_item()))

    def test_critical_failure_rejected_even_if_score_decent(self):
        bad = _good_item(correct_answer="zzz")  # not in options
        # Critical failure: should not pass even though only one rule failed.
        self.assertFalse(question_validator.passes(bad))

    def test_review_required_for_borderline(self):
        # Two non-critical deductions push the score into the 60–80 band.
        # `unresolved_placeholder` (-15) + `blank_run` (-15) = 70.
        item = _good_item(
            question_text="She {{verb}} blank blank blank to school.",
            correct_answer="goes",  # still in options → no critical failure
        )
        self.assertTrue(question_validator.review_required(item))

    def test_annotate_stamps_score_and_metadata(self):
        item = _good_item()
        question_validator.annotate(item)
        self.assertEqual(item["quality_score"], 100)
        self.assertIn("validation", item["metadata"])
        self.assertTrue(item["is_reviewed"])  # high score auto-reviewed


class DuplicateDetectorTests(TestCase):
    def test_hash_question_normalises_punctuation(self):
        a = duplicate_detector.hash_question("She goes home.", "goes")
        b = duplicate_detector.hash_question("She goes home!!!", "goes")
        self.assertEqual(a, b)

    def test_is_duplicate_against_db(self):
        h = duplicate_detector.hash_question("Hi", "x")
        GeneratedQuestion.objects.create(
            code="d-1", question_type="multiple_choice",
            question_text="Hi", correct_answer="x", content_hash=h,
        )
        self.assertTrue(duplicate_detector.is_duplicate(h))
        self.assertFalse(duplicate_detector.is_duplicate("never-seen"))

    def test_bulk_filter_new_subtracts_existing(self):
        h = duplicate_detector.hash_question("dup", "x")
        GeneratedQuestion.objects.create(
            code="d-2", question_type="multiple_choice",
            question_text="dup", correct_answer="x", content_hash=h,
        )
        items = [
            {"content_hash": h, "question_text": "dup", "correct_answer": "x"},
            {"content_hash": "new-hash", "question_text": "novel", "correct_answer": "x"},
        ]
        new_items, dup_count = duplicate_detector.bulk_filter_new(items)
        self.assertEqual(dup_count, 1)
        self.assertEqual({i["content_hash"] for i in new_items}, {"new-hash"})
