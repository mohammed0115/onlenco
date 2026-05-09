from collections import Counter

from django.core.management import call_command
from django.test import TestCase

from learning_core.models import AdaptiveExercise


class SeedExerciseBanksTests(TestCase):
    def test_seed_creates_more_than_1000_exercises(self):
        call_command("seed_exercise_banks", verbosity=0)
        self.assertGreaterEqual(AdaptiveExercise.objects.count(), 1000)

    def test_levels_covered_a0_through_c2(self):
        call_command("seed_exercise_banks", verbosity=0)
        levels = set(AdaptiveExercise.objects.values_list("cefr_level", flat=True).distinct())
        for L in ("A0", "A1", "A2", "B1", "B2", "C1", "C2"):
            self.assertIn(L, levels, f"level {L} missing")

    def test_picture_exercises_present_for_a0_a1(self):
        call_command("seed_exercise_banks", verbosity=0)
        types = set(
            AdaptiveExercise.objects.filter(cefr_level__in=["A0", "A1"])
            .values_list("question_type", flat=True)
        )
        self.assertIn("picture_word", types)
        self.assertIn("picture_verb", types)
        self.assertIn("picture_adjective", types)

    def test_picture_metadata_has_emoji(self):
        call_command("seed_exercise_banks", verbosity=0)
        ex = (
            AdaptiveExercise.objects
            .filter(question_type="picture_word")
            .exclude(metadata={})
            .first()
        )
        self.assertIsNotNone(ex)
        self.assertIn("picture", ex.metadata)
        self.assertTrue(ex.metadata["picture"])

    def test_seed_is_idempotent(self):
        call_command("seed_exercise_banks", verbosity=0)
        n1 = AdaptiveExercise.objects.count()
        call_command("seed_exercise_banks", verbosity=0)
        n2 = AdaptiveExercise.objects.count()
        self.assertEqual(n1, n2, "second run created duplicates")
