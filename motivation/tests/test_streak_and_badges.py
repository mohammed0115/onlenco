from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from motivation.models import LearnerActivitySnapshot, UserBadge
from motivation.services import badge_service, streak_service

User = get_user_model()


class StreakServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="streaker", email="s@x.com", password="pw"
        )

    def test_milestone_detection(self):
        self.assertTrue(streak_service.is_streak_milestone(7))
        self.assertTrue(streak_service.is_streak_milestone(30))
        self.assertFalse(streak_service.is_streak_milestone(2))

    def test_upcoming_milestone(self):
        self.assertEqual(streak_service.upcoming_milestone(0), 3)
        self.assertEqual(streak_service.upcoming_milestone(7), 14)
        self.assertEqual(streak_service.upcoming_milestone(101), None)

    def test_get_current_streak_reads_snapshot(self):
        LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
            current_streak_days=5,
        )
        self.assertEqual(streak_service.get_current_streak(self.user), 5)


class BadgeServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="badger", email="b@x.com", password="pw"
        )

    def test_award_badge_idempotent(self):
        b, created = badge_service.award_badge(
            self.user, badge_code="streak_7", badge_name="7-day streak"
        )
        self.assertTrue(created)
        b2, created2 = badge_service.award_badge(
            self.user, badge_code="streak_7", badge_name="7-day streak"
        )
        self.assertFalse(created2)
        self.assertEqual(b.id, b2.id)
        self.assertEqual(UserBadge.objects.filter(user=self.user).count(), 1)

    def test_streak_badge_for_returns_spec(self):
        spec = badge_service.streak_badge_for(7)
        self.assertEqual(spec["code"], "streak_7")
        self.assertIsNone(badge_service.streak_badge_for(5))
