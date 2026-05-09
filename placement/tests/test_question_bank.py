"""Schema + admin + seed sanity tests for the placement bank."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from placement.models import PlacementQuestion

User = get_user_model()


class SeedCommandTests(TestCase):
    def test_seed_creates_written_and_speaking_pools(self):
        call_command("seed_placement_questions", stdout=StringIO())
        self.assertGreaterEqual(
            PlacementQuestion.objects.filter(question_type="written").count(), 100,
            "spec requires ≥ 100 written questions",
        )
        self.assertGreaterEqual(
            PlacementQuestion.objects.filter(question_type="speaking").count(), 100,
            "spec requires ≥ 100 speaking questions",
        )

    def test_seed_is_idempotent(self):
        call_command("seed_placement_questions", stdout=StringIO())
        first = PlacementQuestion.objects.count()
        call_command("seed_placement_questions", stdout=StringIO())
        self.assertEqual(first, PlacementQuestion.objects.count(),
                         "running seed twice must not duplicate rows")

    def test_seed_covers_required_topic_buckets(self):
        call_command("seed_placement_questions", stdout=StringIO())
        # Written distribution slots
        for topic in ["intro", "grammar_fix", "sentence", "daily", "reason"]:
            self.assertTrue(
                PlacementQuestion.objects.filter(
                    question_type="written", topic=topic, is_active=True,
                ).exists(),
                f"missing written bucket: {topic}",
            )
        # Speaking distribution slots
        for topic in ["name", "age_country", "work_study", "hobby", "reason"]:
            self.assertTrue(
                PlacementQuestion.objects.filter(
                    question_type="speaking", topic=topic, is_active=True,
                ).exists(),
                f"missing speaking bucket: {topic}",
            )


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
