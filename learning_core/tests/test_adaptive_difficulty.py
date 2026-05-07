from django.contrib.auth import get_user_model
from django.test import TestCase

from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    Skill,
    SkillMastery,
    StudentLearningProfile,
)
from learning_core.services import adaptive_difficulty as ad

User = get_user_model()


class AdaptiveDifficultyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="zoe", password="pw")
        self.skill = Skill.objects.create(
            name="Past Simple usage", category="grammar", cefr_level="A2"
        )
        self.exercise = AdaptiveExercise.objects.create(
            skill=self.skill,
            cefr_level="A2",
            difficulty_score=0.5,
            question_type="multiple_choice",
            question="x",
            options=["a", "b"],
            correct_answer="a",
        )

    def _attempt(self, *, correct: bool, score: float | None = None):
        return ExerciseAttempt.objects.create(
            user=self.user,
            exercise=self.exercise,
            user_answer="a" if correct else "b",
            is_correct=correct,
            score=(1.0 if correct else 0.0) if score is None else score,
        )

    def test_expected_score_monotonic(self):
        # Higher theta → higher P(correct) for same difficulty
        self.assertLess(ad.expected_score(-1.0, 0.5), ad.expected_score(1.0, 0.5))
        # Higher difficulty → lower P(correct) for same theta
        self.assertGreater(ad.expected_score(0.0, 0.2), ad.expected_score(0.0, 0.8))

    def test_theta_increases_after_correct_at_average_difficulty(self):
        attempt = self._attempt(correct=True)
        profile = ad.update_theta(self.user, self.exercise, attempt)
        self.assertGreater(profile.theta_score, 0.0)
        self.assertLess(profile.theta_score, 1.0)

    def test_theta_decreases_after_wrong_at_average_difficulty(self):
        attempt = self._attempt(correct=False)
        profile = ad.update_theta(self.user, self.exercise, attempt)
        self.assertLess(profile.theta_score, 0.0)

    def test_theta_clamped_after_repeated_success(self):
        for _ in range(200):
            ad.update_theta(self.user, self.exercise, self._attempt(correct=True))
        profile = StudentLearningProfile.objects.get(user=self.user)
        self.assertLessEqual(profile.theta_score, ad.THETA_MAX)
        self.assertGreater(profile.theta_score, 1.0)

    def test_theta_clamped_after_repeated_failure(self):
        for _ in range(200):
            ad.update_theta(self.user, self.exercise, self._attempt(correct=False))
        profile = StudentLearningProfile.objects.get(user=self.user)
        self.assertGreaterEqual(profile.theta_score, ad.THETA_MIN)
        self.assertLess(profile.theta_score, -1.0)

    def test_skill_mastery_clamps_to_0_100(self):
        for _ in range(50):
            ad.update_skill_mastery(self.user, self.skill, self._attempt(correct=True))
        m = SkillMastery.objects.get(user=self.user, skill=self.skill)
        self.assertLessEqual(m.mastery_score, 100.0)
        self.assertGreater(m.mastery_score, 0.0)

        for _ in range(100):
            ad.update_skill_mastery(self.user, self.skill, self._attempt(correct=False))
        m.refresh_from_db()
        self.assertGreaterEqual(m.mastery_score, 0.0)

    def test_recommend_difficulty_above_easy_for_high_theta(self):
        StudentLearningProfile.objects.update_or_create(
            user=self.user, defaults={"theta_score": 1.5}
        )
        d = ad.recommend_next_difficulty(self.user, target_p=0.7)
        self.assertGreater(d, 0.5)
        self.assertLess(d, 0.95)

    def test_get_learning_state_shape(self):
        ad.update_theta(self.user, self.exercise, self._attempt(correct=True))
        ad.update_skill_mastery(self.user, self.skill, self._attempt(correct=True))
        state = ad.get_learning_state(self.user)
        self.assertIn("theta_score", state)
        self.assertIn("cefr_level", state)
        self.assertIn("recommended_difficulty", state)
        self.assertIsInstance(state["strongest_skills"], list)

    def test_process_attempt_updates_both(self):
        attempt = self._attempt(correct=True)
        result = ad.process_attempt(self.user, self.exercise, attempt)
        self.assertGreater(result["theta_score"], 0.0)
        self.assertIsNotNone(result["mastery_score"])
        self.assertEqual(SkillMastery.objects.get(user=self.user, skill=self.skill).attempts_count, 1)
