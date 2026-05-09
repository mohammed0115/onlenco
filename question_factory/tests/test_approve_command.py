"""Tests for `approve_questions_for_training`."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from question_factory.models import GeneratedQuestion


def _gq(*, code, quality=85, reviewed=True, active=True,
        cefr="A1", skill="grammar"):
    return GeneratedQuestion.objects.create(
        code=code, question_type="multiple_choice",
        cefr_level=cefr, skill=skill,
        question_text=f"q-{code}", correct_answer="ok",
        options=["a", "b", "c", "ok"],
        quality_score=quality,
        is_active=active, is_reviewed=reviewed,
        approved_for_training=False,
        content_hash=f"h-{code}",
    )


class ApproveQuestionsForTrainingTests(TestCase):
    def setUp(self):
        _gq(code="hi-q", quality=90)             # eligible
        _gq(code="mid-q", quality=80)            # eligible (boundary)
        _gq(code="low-q", quality=70)            # below default min-quality
        _gq(code="unrev", quality=90, reviewed=False)   # not reviewed
        _gq(code="inactive", quality=90, active=False)  # inactive

    def test_dry_run_writes_nothing(self):
        call_command("approve_questions_for_training", "--dry-run",
                     stdout=StringIO())
        self.assertEqual(
            GeneratedQuestion.objects.filter(approved_for_training=True).count(),
            0,
        )

    def test_default_threshold_approves_only_eligible(self):
        call_command("approve_questions_for_training", stdout=StringIO())
        approved = list(
            GeneratedQuestion.objects
            .filter(approved_for_training=True)
            .values_list("code", flat=True)
        )
        self.assertCountEqual(approved, ["hi-q", "mid-q"])

    def test_lower_threshold_includes_more(self):
        call_command("approve_questions_for_training", "--min-quality", "70",
                     stdout=StringIO())
        approved = set(
            GeneratedQuestion.objects
            .filter(approved_for_training=True)
            .values_list("code", flat=True)
        )
        self.assertEqual(approved, {"hi-q", "mid-q", "low-q"})

    def test_include_unreviewed_flag(self):
        call_command("approve_questions_for_training",
                     "--include-unreviewed", stdout=StringIO())
        approved = set(
            GeneratedQuestion.objects
            .filter(approved_for_training=True)
            .values_list("code", flat=True)
        )
        self.assertIn("unrev", approved)

    def test_skill_filter(self):
        _gq(code="vocab-q", quality=90, skill="vocabulary")
        call_command("approve_questions_for_training",
                     "--skill", "vocabulary", stdout=StringIO())
        approved = set(
            GeneratedQuestion.objects
            .filter(approved_for_training=True)
            .values_list("code", flat=True)
        )
        self.assertEqual(approved, {"vocab-q"})

    def test_idempotent(self):
        call_command("approve_questions_for_training", stdout=StringIO())
        n1 = GeneratedQuestion.objects.filter(approved_for_training=True).count()
        call_command("approve_questions_for_training", stdout=StringIO())
        n2 = GeneratedQuestion.objects.filter(approved_for_training=True).count()
        self.assertEqual(n1, n2)
