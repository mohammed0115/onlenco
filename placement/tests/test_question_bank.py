"""Schema + admin + seed sanity tests for the placement bank."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from placement.models import PlacementQuestion

User = get_user_model()


class SeedCommandTests(TestCase):
    def test_seed_creates_written_and_speaking_pools(self):
        # Curated bank: exactly 5 written MCQ + 5 spoken.
        call_command("seed_placement_questions", stdout=StringIO())
        self.assertEqual(PlacementQuestion.objects.filter(question_type="written", is_active=True).count(), 5)
        self.assertEqual(PlacementQuestion.objects.filter(question_type="speaking", is_active=True).count(), 5)

    def test_seed_is_idempotent(self):
        call_command("seed_placement_questions", stdout=StringIO())
        first = PlacementQuestion.objects.count()
        call_command("seed_placement_questions", stdout=StringIO())
        self.assertEqual(first, PlacementQuestion.objects.count(),
                         "running seed twice must not duplicate rows")

    def test_seed_written_are_mcq_with_answer_key(self):
        call_command("seed_placement_questions", stdout=StringIO())
        for q in PlacementQuestion.objects.filter(question_type="written", is_active=True):
            self.assertEqual(q.expected_answer_type, "mcq")
            self.assertTrue(any(o.get("is_correct") for o in q.options))


class PlacementQuestionTextForLanguageTests(TestCase):
    def test_arabic_returns_arabic_when_set(self):
        q = PlacementQuestion.objects.create(
            code="t.x.001", question_type="written", skill="writing",
            question_text="Hello", question_text_ar="مرحبا",
        )
        self.assertEqual(q.text_for("ar"), "مرحبا")

    def test_arabic_falls_back_to_english_when_ar_blank(self):
        q = PlacementQuestion.objects.create(
            code="t.x.002", question_type="written", skill="writing",
            question_text="Hello", question_text_ar="",
        )
        self.assertEqual(q.text_for("ar"), "Hello")

    def test_english_always_returns_english(self):
        q = PlacementQuestion.objects.create(
            code="t.x.003", question_type="written", skill="writing",
            question_text="Hello", question_text_ar="مرحبا",
        )
        self.assertEqual(q.text_for("en"), "Hello")
