from django.test import TestCase

from exams.services.duplicate_detection import (
    bulk_filter_new,
    hash_text,
    is_duplicate,
    normalise_text,
)
from learning_core.models import AdaptiveExercise


class DuplicateDetectionTests(TestCase):
    def test_normalise_strips_punctuation(self):
        self.assertEqual(normalise_text("Hello, World!"), "hello world")
        self.assertEqual(normalise_text("She  ___  goes!"), "she goes")

    def test_hash_stable_across_punctuation_variations(self):
        a = hash_text("She goes home.")
        b = hash_text("She goes home!!!")
        self.assertEqual(a, b)

    def test_is_duplicate_detects_db_match(self):
        AdaptiveExercise.objects.create(
            cefr_level="A1", question_type="multiple_choice",
            question="She goes home.", correct_answer="goes",
            text_hash=hash_text("She goes home.|goes"),
        )
        self.assertTrue(is_duplicate(hash_text("She goes home.|goes")))
        self.assertFalse(is_duplicate(hash_text("She runs home.|runs")))

    def test_bulk_filter_new_subtracts_existing(self):
        AdaptiveExercise.objects.create(
            cefr_level="A1", question_type="multiple_choice",
            question="dup", correct_answer="x",
            text_hash="hash-a",
        )
        items = [
            {"text_hash": "hash-a", "question": "dup", "correct_answer": "x"},
            {"text_hash": "hash-b", "question": "new", "correct_answer": "x"},
        ]
        new_items, dups = bulk_filter_new(items)
        self.assertEqual(dups, 1)
        self.assertEqual({i["text_hash"] for i in new_items}, {"hash-b"})
