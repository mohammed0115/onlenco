from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from motivation.models import (
    LearnerActivitySnapshot,
    MotivationMessage,
    UserAchievement,
    UserBadge,
    UserXP,
)

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class MotivationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="api@x.com", email="api@x.com", password="pw"
        )
        self.client.login(username="api@x.com", password="pw")

    def test_xp_endpoint(self):
        UserXP.objects.create(user=self.user, total_xp=120, level_number=2, weekly_xp=40)
        resp = self.client.get(reverse("motivation_api:xp"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total_xp"], 120)
        self.assertEqual(data["level_number"], 2)
        self.assertIn("current_streak", data)

    def test_achievements_endpoint_isolates_users(self):
        from motivation.models import Achievement
        ach = Achievement.objects.create(
            code="x", name="X", category="lesson", threshold_value=1, xp_reward=10,
        )
        UserAchievement.objects.create(user=self.user, achievement=ach)

        other = User.objects.create_user(username="o@x.com", email="o@x.com", password="pw")
        UserAchievement.objects.create(user=other, achievement=ach)

        resp = self.client.get(reverse("motivation_api:achievements"))
        data = resp.json()
        results = data.get("results") or data
        self.assertEqual(len(results), 1)

    def test_badges_endpoint(self):
        UserBadge.objects.create(user=self.user, badge_code="streak_7", badge_name="7-day streak")
        resp = self.client.get(reverse("motivation_api:badges"))
        data = resp.json()
        results = data.get("results") or data
        self.assertEqual(len(results), 1)

    def test_run_endpoint_creates_snapshot(self):
        resp = self.client.post(reverse("motivation_api:run"))
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertTrue(LearnerActivitySnapshot.objects.filter(user=self.user).exists())
