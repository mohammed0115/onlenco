from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from motivation.models import (
    Challenge,
    ChallengeProgress,
    LeaderboardEntry,
    LearnerActivitySnapshot,
    MotivationPreference,
    UserXP,
)
from motivation.services import challenge_service, leaderboard_service

User = get_user_model()


class ChallengeServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ch@x.com", email="ch@x.com", password="pw"
        )

    def test_seed_creates_default_challenges(self):
        n = challenge_service.seed_default_challenges()
        self.assertGreaterEqual(n, 4)
        # Re-running is idempotent.
        self.assertEqual(challenge_service.seed_default_challenges(), 0)

    def test_tick_advances_progress_and_awards_xp_on_completion(self):
        today = timezone.localdate()
        ch = Challenge.objects.create(
            code="weekly_test", title="t", kind="weekly",
            metric="lessons_completed", target_value=3, xp_reward=50,
            start_at=today - timedelta(days=2), end_at=today + timedelta(days=4),
        )
        for i in range(3):
            LearnerActivitySnapshot.objects.create(
                user=self.user, date=today - timedelta(days=i),
                lessons_completed=1,
            )
        progress = challenge_service.tick_for_user(self.user)
        self.assertEqual(len(progress), 1)
        p = progress[0]
        self.assertEqual(p.current_value, 3)
        self.assertIsNotNone(p.completed_at)
        # XP credited
        xp = UserXP.objects.get(user=self.user)
        self.assertEqual(xp.total_xp, 50)
        # Re-tick doesn't double-award
        challenge_service.tick_for_user(self.user)
        xp.refresh_from_db()
        self.assertEqual(xp.total_xp, 50)


class LeaderboardServiceTests(TestCase):
    def test_only_opted_in_users_appear(self):
        today = timezone.localdate()
        u1 = User.objects.create_user(username="a@x.com", email="a@x.com", password="pw")
        u2 = User.objects.create_user(username="b@x.com", email="b@x.com", password="pw")
        # u1 opts in (default True), u2 opts out
        MotivationPreference.objects.update_or_create(
            user=u2, defaults={"show_on_leaderboard": False},
        )
        for u in (u1, u2):
            LearnerActivitySnapshot.objects.create(
                user=u, date=today,
                lessons_completed=1,
                metadata={"xp_awarded": 100},
            )
        rebuilt = leaderboard_service.rebuild_period("weekly", today)
        self.assertEqual(rebuilt, 1)
        entries = leaderboard_service.top_n("weekly", n=10, today=today)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].user_id, u1.id)

    def test_user_entry_returns_none_for_opted_out(self):
        today = timezone.localdate()
        u = User.objects.create_user(username="c@x.com", email="c@x.com", password="pw")
        MotivationPreference.objects.create(user=u, show_on_leaderboard=False)
        LearnerActivitySnapshot.objects.create(
            user=u, date=today, metadata={"xp_awarded": 50},
        )
        leaderboard_service.rebuild_period("weekly", today)
        self.assertIsNone(leaderboard_service.user_entry(u, "weekly", today))
