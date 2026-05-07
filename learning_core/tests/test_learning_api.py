from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from learning_core.models import (
    AdaptiveExercise,
    Skill,
    SkillMastery,
    UserError,
    UserWeakness,
)

User = get_user_model()


@override_settings(AI_API_KEY="")
class LearningCoreApiTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pw")
        self.bob = User.objects.create_user(username="bob", password="pw")
        self.skill = Skill.objects.create(
            name="Reading core", category="reading", cefr_level="A2"
        )
        SkillMastery.objects.create(user=self.alice, skill=self.skill, mastery_score=42)
        UserError.objects.create(
            user=self.alice,
            source_type="quiz",
            error_type="grammar",
            severity=4,
            skill=self.skill,
        )
        UserWeakness.objects.create(
            user=self.alice,
            skill=self.skill,
            weakness_score=30,
            priority_score=30,
            status="active",
        )
        self.exercise = AdaptiveExercise.objects.create(
            skill=self.skill,
            cefr_level="A2",
            difficulty_score=0.4,
            question_type="multiple_choice",
            question="X?",
            options=["a", "b"],
            correct_answer="a",
        )

    def test_unauthenticated_blocked(self):
        for url_name in (
            "learning_api:profile",
            "learning_api:mastery",
            "learning_api:weaknesses",
            "learning_api:errors",
            "learning_api:recommendations",
        ):
            r = self.client.get(reverse(url_name))
            self.assertIn(r.status_code, (401, 403))

    def test_profile_returns_state(self):
        self.client.force_login(self.alice)
        r = self.client.get(reverse("learning_api:profile"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("state", r.json())
        self.assertIn("theta_score", r.json()["state"])

    def test_mastery_returns_only_my_rows(self):
        SkillMastery.objects.create(user=self.bob, skill=self.skill, mastery_score=10)
        self.client.force_login(self.alice)
        r = self.client.get(reverse("learning_api:mastery"))
        ids = {row["id"] for row in r.json()}
        self.assertEqual(len(ids), 1)

    def test_errors_returns_only_my_rows(self):
        UserError.objects.create(
            user=self.bob, source_type="quiz", error_type="grammar", severity=3
        )
        self.client.force_login(self.alice)
        r = self.client.get(reverse("learning_api:errors"))
        self.assertEqual(len(r.json()), 1)

    def test_weaknesses_returns_only_my_rows(self):
        UserWeakness.objects.create(
            user=self.bob, skill=self.skill, weakness_score=20, priority_score=20
        )
        self.client.force_login(self.alice)
        r = self.client.get(reverse("learning_api:weaknesses"))
        self.assertEqual(len(r.json()), 1)

    def test_attempt_endpoint_grades_and_updates(self):
        self.client.force_login(self.alice)
        r = self.client.post(
            reverse("learning_api:exercises_attempt", args=[self.exercise.id]),
            data={"user_answer": "a", "time_spent_seconds": 5},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertTrue(body["is_correct"])
        self.assertIn("theta_score", body)
        self.assertIn("cefr_level", body)

    def test_attempt_wrong_answer_marks_incorrect(self):
        self.client.force_login(self.alice)
        r = self.client.post(
            reverse("learning_api:exercises_attempt", args=[self.exercise.id]),
            data={"user_answer": "b", "time_spent_seconds": 3},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertFalse(r.json()["is_correct"])

    def test_generate_exercises_endpoint(self):
        self.client.force_login(self.alice)
        r = self.client.post(
            reverse("learning_api:exercises_generate"),
            data={"count_per_weakness": 2},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertGreaterEqual(len(r.json()), 1)

    def test_analyze_text_endpoint(self):
        self.client.force_login(self.alice)
        r = self.client.post(
            reverse("learning_api:analyze_text"),
            data={"text": "I goes home", "source_type": "writing"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn("errors", body)

    def test_next_exercise_returns_one(self):
        self.client.force_login(self.alice)
        r = self.client.get(reverse("learning_api:exercises_next"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["id"], self.exercise.id)
