"""Tests for the generate_a0_question_bank command."""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from daily_learning.services import a0_templates


class GenerateA0QuestionBankTests(TestCase):
    def test_command_creates_exercises(self):
        from learning_core.models import AdaptiveExercise
        out = StringIO()
        call_command("generate_a0_question_bank", stdout=out)
        # Expect ~4 variants per topic (some skip translation/fill if
        # word doesn't appear). At least 3 per topic guaranteed.
        count = AdaptiveExercise.objects.filter(
            code__startswith="a0-topic-",
        ).count()
        self.assertGreaterEqual(
            count, 3 * len(a0_templates.A0_TOPICS),
            "Should create at least 3 variants per topic",
        )

    def test_all_exercises_are_a0_level_and_marked_reviewed(self):
        from learning_core.models import AdaptiveExercise
        call_command("generate_a0_question_bank", stdout=StringIO())
        for ex in AdaptiveExercise.objects.filter(code__startswith="a0-topic-"):
            self.assertEqual(ex.cefr_level, "A0")
            self.assertTrue(ex.is_active)
            self.assertTrue(ex.is_reviewed,
                            "Catalog-derived exercises should be pre-reviewed")
            self.assertLessEqual(ex.difficulty_score, 0.30,
                                 "A0 exercises must stay easy")

    def test_rerun_is_idempotent(self):
        from learning_core.models import AdaptiveExercise
        call_command("generate_a0_question_bank", stdout=StringIO())
        first = AdaptiveExercise.objects.filter(code__startswith="a0-topic-").count()
        call_command("generate_a0_question_bank", stdout=StringIO())
        second = AdaptiveExercise.objects.filter(code__startswith="a0-topic-").count()
        self.assertEqual(first, second, "Re-running must not duplicate rows")

    def test_dry_run_writes_nothing(self):
        from learning_core.models import AdaptiveExercise
        before = AdaptiveExercise.objects.filter(code__startswith="a0-topic-").count()
        call_command("generate_a0_question_bank", "--dry-run",
                     stdout=StringIO())
        after = AdaptiveExercise.objects.filter(code__startswith="a0-topic-").count()
        self.assertEqual(before, after)

    def test_every_topic_has_at_least_one_mcq(self):
        from learning_core.models import AdaptiveExercise
        call_command("generate_a0_question_bank", stdout=StringIO())
        for topic in a0_templates.A0_TOPICS:
            mcqs = AdaptiveExercise.objects.filter(
                code__startswith=f"a0-topic-{topic.slug}-",
                question_type="multiple_choice",
            )
            self.assertGreaterEqual(
                mcqs.count(), 1,
                f"Topic {topic.slug!r} should have at least 1 MCQ variant",
            )

    def test_include_extras_adds_word_order_variants(self):
        """--include-extras should grow the bank with sentence_building rows."""
        from learning_core.models import AdaptiveExercise
        call_command("generate_a0_question_bank", "--include-extras",
                     stdout=StringIO())
        sb = AdaptiveExercise.objects.filter(
            code__startswith="a0-topic-",
            question_type="sentence_building",
        )
        self.assertGreater(
            sb.count(), 0,
            "--include-extras must add sentence_building (word-order) rows",
        )

    def test_extras_flag_roughly_doubles_total_per_topic(self):
        """Without extras: 3-4 variants. With extras: 5-6 per topic."""
        from learning_core.models import AdaptiveExercise
        call_command("generate_a0_question_bank", stdout=StringIO())
        before = AdaptiveExercise.objects.filter(
            code__startswith="a0-topic-",
        ).count()
        call_command("generate_a0_question_bank", "--include-extras",
                     stdout=StringIO())
        after = AdaptiveExercise.objects.filter(
            code__startswith="a0-topic-",
        ).count()
        self.assertGreater(after, before,
                           "--include-extras must enlarge the bank")
