from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from learning_core.models import Skill, SkillMastery, UserError, UserWeakness

User = get_user_model()


@override_settings(AI_API_KEY="")
class CrossUserIsolationTests(TestCase):
    """Confirm one user cannot read another user's adaptive learning data."""

    def setUp(self):
        self.alice = User.objects.create_user(username="alice", password="pw")
        self.bob = User.objects.create_user(username="bob", password="pw")
        self.skill = Skill.objects.create(
            name="Reading core", category="reading", cefr_level="A2"
        )
        SkillMastery.objects.create(user=self.alice, skill=self.skill, mastery_score=42)
        SkillMastery.objects.create(user=self.bob, skill=self.skill, mastery_score=99)
        UserError.objects.create(
            user=self.bob, source_type="quiz", error_type="grammar", severity=5
        )
        UserWeakness.objects.create(
            user=self.bob, skill=self.skill, weakness_score=50, priority_score=50
        )

    def test_alice_does_not_see_bobs_mastery(self):
        self.client.force_login(self.alice)
        r = self.client.get(reverse("learning_api:mastery"))
        scores = [row["mastery_score"] for row in r.json()]
        self.assertNotIn(99.0, scores)
        self.assertEqual(len(scores), 1)

    def test_alice_does_not_see_bobs_errors(self):
        self.client.force_login(self.alice)
        r = self.client.get(reverse("learning_api:errors"))
        self.assertEqual(r.json(), [])

    def test_alice_does_not_see_bobs_weaknesses(self):
        self.client.force_login(self.alice)
        r = self.client.get(reverse("learning_api:weaknesses"))
        self.assertEqual(r.json(), [])
