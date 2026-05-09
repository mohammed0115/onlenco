from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from motivation import constants as C
from motivation.models import LearnerActivitySnapshot, UserXP
from motivation.services import xp_service

User = get_user_model()


class XPServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="xpuser", email="xp@x.com", password="pw"
        )

    def test_award_xp_creates_row(self):
        xp = xp_service.award_xp(self.user, 30)
        self.assertEqual(xp.total_xp, 30)
        self.assertEqual(xp.weekly_xp, 30)
        self.assertEqual(xp.monthly_xp, 30)

    def test_level_increments_with_xp(self):
        xp = xp_service.award_xp(self.user, C.XP_PER_LEVEL * 3)
        self.assertEqual(xp.level_number, 4)  # floor(300/100)+1

    def test_award_for_snapshot_idempotent(self):
        snap = LearnerActivitySnapshot.objects.create(
            user=self.user,
            date=timezone.localdate(),
            lessons_completed=2,
            questions_answered=10,
            quiz_accuracy=80.0,
        )
        total1, _, xp1 = xp_service.award_for_snapshot(snap)
        total2, _, xp2 = xp_service.award_for_snapshot(snap)
        self.assertGreater(total1, 0)
        self.assertEqual(total2, 0)  # second call is a no-op
        snap.refresh_from_db()
        self.assertEqual(snap.metadata.get("xp_awarded"), total1)

    def test_weekly_bucket_resets_on_new_week(self):
        last_week_monday = timezone.localdate() - timedelta(days=14)
        UserXP.objects.create(
            user=self.user,
            total_xp=200,
            weekly_xp=120,
            weekly_xp_reset_at=last_week_monday,
        )
        xp = xp_service.award_xp(self.user, 10)
        self.assertEqual(xp.weekly_xp, 10)  # reset then incremented
        self.assertEqual(xp.total_xp, 210)
