"""Behavioral analytics scoring tests."""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from motivation.models import LearnerActivitySnapshot
from motivation.services import risk_engine


User = get_user_model()


def _make_snapshot(user, **overrides) -> LearnerActivitySnapshot:
    return LearnerActivitySnapshot.objects.create(
        user=user, date=timezone.localdate(), **overrides,
    )


class EngagementScoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="e@x.com", email="e@x.com", password="pw")

    def test_zero_activity_zero_engagement(self):
        snap = _make_snapshot(self.user)
        self.assertEqual(risk_engine.compute_engagement_score(snap), 0.0)

    def test_full_activity_max_engagement(self):
        snap = _make_snapshot(
            self.user,
            lessons_completed=1, ai_chat_minutes=10,
            current_streak_days=7, reading_minutes=10,
            quiz_accuracy=80.0,
        )
        self.assertEqual(risk_engine.compute_engagement_score(snap), 100.0)

    def test_partial_activity_proportional(self):
        snap = _make_snapshot(
            self.user, lessons_completed=1,  # 30% weight @ full = 30
        )
        self.assertEqual(risk_engine.compute_engagement_score(snap), 30.0)


class ChurnRiskScoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="c@x.com", email="c@x.com", password="pw")

    def test_active_engaged_user_low_risk(self):
        snap = _make_snapshot(
            self.user,
            lessons_completed=1, ai_chat_minutes=10,
            current_streak_days=7, reading_minutes=10,
            quiz_accuracy=80.0, inactive_days=0,
        )
        risk = risk_engine.compute_churn_risk_score(snap)
        self.assertLess(risk, 20.0)

    def test_two_week_inactive_high_risk(self):
        snap = _make_snapshot(self.user, inactive_days=14)
        risk = risk_engine.compute_churn_risk_score(snap)
        self.assertGreaterEqual(risk, 60.0)

    def test_no_streak_plus_low_engagement_adds_up(self):
        snap = _make_snapshot(self.user, current_streak_days=0)
        risk = risk_engine.compute_churn_risk_score(snap)
        # No streak (+10) + engagement<30 (+25) + no recent lessons (+15) = 50
        self.assertEqual(risk, 50.0)

    def test_capped_at_100(self):
        snap = _make_snapshot(self.user, inactive_days=30, current_streak_days=0)
        risk = risk_engine.compute_churn_risk_score(snap)
        self.assertLessEqual(risk, 100.0)


class PersistenceAndQueryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="p@x.com", email="p@x.com", password="pw")
        self.snap = _make_snapshot(self.user, inactive_days=10, current_streak_days=0)

    def test_compute_and_persist_writes_both_scores(self):
        snap = risk_engine.compute_and_persist_for(self.snap)
        snap.refresh_from_db()
        self.assertGreater(snap.churn_risk_score, 0.0)

    def test_at_risk_users_query(self):
        risk_engine.compute_and_persist_for(self.snap)
        at_risk = list(risk_engine.at_risk_users(threshold=30.0))
        self.assertEqual(len(at_risk), 1)
        self.assertEqual(at_risk[0].user_id, self.user.pk)

    def test_run_nightly_updates_all_today_snapshots(self):
        # Add a second user
        u2 = User.objects.create_user(username="p2@x.com", email="p2@x.com", password="pw")
        _make_snapshot(u2)
        n = risk_engine.run_nightly()
        self.assertEqual(n, 2)

    def test_old_snapshot_ignored_by_at_risk(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        u3 = User.objects.create_user(username="p3@x.com", email="p3@x.com", password="pw")
        LearnerActivitySnapshot.objects.create(
            user=u3, date=yesterday,
            inactive_days=30, churn_risk_score=90.0,
        )
        risk_engine.compute_and_persist_for(self.snap)
        at_risk = list(risk_engine.at_risk_users(threshold=30.0))
        # Only the user with TODAY's snapshot at risk.
        self.assertEqual({s.user_id for s in at_risk}, {self.user.pk})

    def test_compute_for_user_with_no_snapshot_returns_none(self):
        u_new = User.objects.create_user(username="ns@x.com", email="ns@x.com", password="pw")
        self.assertIsNone(risk_engine.compute_for_user(u_new))
