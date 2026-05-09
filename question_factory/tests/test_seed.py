"""Verify the seed_question_blueprints command meets the spec coverage."""
from django.core.management import call_command
from django.test import TestCase

from question_factory import constants as C
from question_factory.models import QuestionBlueprint


class SeedQuestionBlueprintsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_question_blueprints")

    def test_seed_creates_blueprints_for_every_cefr_level(self):
        for L in ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]:
            self.assertTrue(
                QuestionBlueprint.objects.filter(cefr_level=L).exists(),
                f"No blueprints seeded for CEFR level {L}",
            )

    def test_seed_meets_per_level_minimum(self):
        # Spec: 20 blueprints per CEFR level (10 grammar + 10 vocab).
        for L in ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]:
            n = QuestionBlueprint.objects.filter(cefr_level=L).count()
            self.assertGreaterEqual(
                n, 20, f"Level {L} has only {n} blueprints (need >= 20)",
            )

    def test_seed_includes_grammar_and_vocab_per_level(self):
        for L in ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]:
            grammar = QuestionBlueprint.objects.filter(
                cefr_level=L, skill=C.SKILL_GRAMMAR,
            ).count()
            vocab = QuestionBlueprint.objects.filter(
                cefr_level=L, skill=C.SKILL_VOCABULARY,
            ).count()
            self.assertGreaterEqual(grammar, 10, f"Level {L} grammar < 10")
            self.assertGreaterEqual(vocab, 10, f"Level {L} vocab < 10")

    def test_seed_includes_reading_writing_speaking(self):
        self.assertTrue(QuestionBlueprint.objects.filter(skill=C.SKILL_READING).exists())
        self.assertTrue(QuestionBlueprint.objects.filter(skill=C.SKILL_WRITING).exists())
        self.assertTrue(QuestionBlueprint.objects.filter(skill=C.SKILL_SPEAKING).exists())

    def test_seed_is_idempotent(self):
        n1 = QuestionBlueprint.objects.count()
        call_command("seed_question_blueprints")
        n2 = QuestionBlueprint.objects.count()
        self.assertEqual(n1, n2)
