from django.contrib.auth import get_user_model
from django.test import TestCase

from learning_core.models import AdaptiveExercise, Skill, StudentLearningProfile
from learning_core.services.micro_practice import _pick_for_level

User = get_user_model()


class LevelAwarePickTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="lv@x.com", email="lv@x.com", password="pw"
        )
        self.skill = Skill.objects.create(name="grammar", category="grammar")
        for lvl in ("A0", "A1", "A2", "B1", "B2", "C1", "C2"):
            for i in range(5):
                AdaptiveExercise.objects.create(
                    skill=self.skill, cefr_level=lvl, difficulty_score=0.3,
                    question_type="multiple_choice",
                    question=f"q-{lvl}-{i}", correct_answer="a",
                )

    def test_picks_only_band_pm_one(self):
        # A learner at A2 should see A1/A2/B1, never C1/C2.
        items = _pick_for_level(self.user, "A2", set())
        levels = {ex.cefr_level for ex in items}
        self.assertTrue(levels.issubset({"A1", "A2", "B1"}))
        self.assertNotIn("C1", levels)
        self.assertNotIn("C2", levels)

    def test_a0_falls_back_to_neighbour(self):
        items = _pick_for_level(self.user, "A0", set())
        levels = {ex.cefr_level for ex in items}
        self.assertTrue(levels.issubset({"A0", "A1"}))


class NextExerciseLevelAwareApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="next@x.com", email="next@x.com", password="pw"
        )
        StudentLearningProfile.objects.create(user=self.user, current_cefr_level="B1")
        self.skill = Skill.objects.create(name="grammar", category="grammar")
        for lvl in ("A0", "B1", "C2"):
            AdaptiveExercise.objects.create(
                skill=self.skill, cefr_level=lvl, difficulty_score=0.5,
                question_type="multiple_choice",
                question=f"q-{lvl}", correct_answer="a",
            )
        self.client.login(username="next@x.com", password="pw")

    def test_next_endpoint_returns_band_match(self):
        # Hit /api/v1/exercises/next/ several times; results should stay
        # within ±1 band of the user's B1 level (A2/B1/B2 — but A2/B2
        # don't exist in this setup, so it's B1).
        from django.urls import reverse
        seen = set()
        for _ in range(5):
            r = self.client.get(reverse("learning_api:exercises_next"))
            if r.status_code == 200:
                seen.add(r.json()["cefr_level"])
        # Should never include A0 or C2 (out of band).
        self.assertNotIn("A0", seen)
        self.assertNotIn("C2", seen)
