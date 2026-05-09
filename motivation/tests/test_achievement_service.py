from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from motivation.models import (
    Achievement,
    LearnerActivitySnapshot,
    UserAchievement,
)
from motivation.services import achievement_service

User = get_user_model()


class AchievementServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_achievements")

    def setUp(self):
        self.user = User.objects.create_user(
            username="achiever", email="a@x.com", password="pw"
        )

    def test_seed_creates_achievements(self):
        self.assertGreater(Achievement.objects.count(), 5)

    def test_first_lesson_awarded_when_threshold_met(self):
        snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
            lessons_completed=1,
        )
        earned = achievement_service.evaluate_for_snapshot(snap)
        codes = [ua.achievement.code for ua in earned]
        self.assertIn("first_lesson_completed", codes)

    def test_award_idempotent(self):
        snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
            lessons_completed=1,
        )
        achievement_service.evaluate_for_snapshot(snap)
        achievement_service.evaluate_for_snapshot(snap)
        self.assertEqual(
            UserAchievement.objects.filter(
                user=self.user, achievement__code="first_lesson_completed"
            ).count(),
            1,
        )

    def test_award_by_code_xp_credited(self):
        ua, created = achievement_service.award_by_code(self.user, "first_lesson_completed")
        self.assertTrue(created)
        # XP should be credited
        from motivation.models import UserXP
        xp = UserXP.objects.get(user=self.user)
        self.assertGreater(xp.total_xp, 0)
