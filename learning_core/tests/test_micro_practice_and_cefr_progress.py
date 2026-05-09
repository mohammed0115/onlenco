from django.contrib.auth import get_user_model
from django.test import TestCase

from learning_core.models import AdaptiveExercise, Skill, StudentLearningProfile
from learning_core.services.adaptive_difficulty import cefr_progress
from learning_core.services.micro_practice import micro_practice

User = get_user_model()


class CefrProgressTests(TestCase):
    def test_a0_at_low_theta(self):
        p = cefr_progress(-3.0)
        self.assertEqual(p["current"], "A0")

    def test_b1_band_progress(self):
        p = cefr_progress(0.0)  # in B1 band (-0.5 to 0.5)
        self.assertEqual(p["current"], "B1")
        self.assertEqual(p["next"], "B2")
        self.assertGreater(p["percent"], 30)
        self.assertLess(p["percent"], 70)

    def test_c2_no_next(self):
        # theta in [2.4, 2.8) → C2 band per learning_core's mapping
        p = cefr_progress(2.6)
        self.assertEqual(p["current"], "C2")


class MicroPracticeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="mp@x.com", email="mp@x.com", password="pw"
        )
        StudentLearningProfile.objects.create(user=self.user, current_cefr_level="A2")
        self.skill = Skill.objects.create(name="reading", category="reading")
        for i in range(5):
            AdaptiveExercise.objects.create(
                skill=self.skill, cefr_level="A2", difficulty_score=0.5,
                question_type="multiple_choice",
                question=f"q{i}", correct_answer="a",
            )

    def test_returns_n_items_at_users_level(self):
        items = micro_practice(self.user, count=3)
        self.assertEqual(len(items), 3)
        for ex in items:
            self.assertEqual(ex.cefr_level, "A2")

    def test_does_not_return_already_attempted(self):
        from learning_core.models import ExerciseAttempt
        ex0 = AdaptiveExercise.objects.first()
        ExerciseAttempt.objects.create(
            user=self.user, exercise=ex0, user_answer="a",
            is_correct=True, score=1.0,
        )
        items = micro_practice(self.user, count=3)
        self.assertNotIn(ex0.id, [i.id for i in items])
