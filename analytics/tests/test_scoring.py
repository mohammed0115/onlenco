"""Tests for the new behavioral scoring services."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from analytics.services.scoring import (
    churn_risk,
    engagement_score,
    improvement_trend,
    learning_speed_for,
    persist_for_user,
)
from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    SkillMastery,
    Skill,
    StudentLearningProfile,
)
from motivation.models import LearnerActivitySnapshot

User = get_user_model()


class EngagementScoreTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="engage@x.com", email="engage@x.com", password="pw"
        )

    def test_zero_for_no_activity(self):
        self.assertEqual(engagement_score(self.user), 0)

    def test_high_for_daily_consistent_user(self):
        today = timezone.localdate()
        for i in range(14):
            LearnerActivitySnapshot.objects.create(
                user=self.user,
                date=today - timedelta(days=i),
                lessons_completed=2,
                questions_answered=10,
                quiz_accuracy=80.0,
                current_streak_days=i + 1,
                ai_chat_minutes=10,
            )
        self.assertGreater(engagement_score(self.user, days=14), 60)


class ChurnRiskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ch@x.com", email="ch@x.com", password="pw"
        )

    def test_high_for_long_inactivity(self):
        old = timezone.localdate() - timedelta(days=15)
        LearnerActivitySnapshot.objects.create(
            user=self.user, date=old, lessons_completed=1,
        )
        self.assertEqual(churn_risk(self.user), "high")

    def test_low_for_recently_active(self):
        today = timezone.localdate()
        # Active every day for two weeks → high engagement → low churn risk
        for i in range(14):
            LearnerActivitySnapshot.objects.create(
                user=self.user, date=today - timedelta(days=i),
                lessons_completed=2, questions_answered=10, quiz_accuracy=85.0,
                current_streak_days=i + 1, ai_chat_minutes=15,
            )
        self.assertEqual(churn_risk(self.user), "low")

    def test_no_history_returns_medium(self):
        self.assertEqual(churn_risk(self.user), "medium")


class LearningSpeedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ls@x.com", email="ls@x.com", password="pw"
        )
        self.skill = Skill.objects.create(name="reading", category="reading")
        self.ex = AdaptiveExercise.objects.create(
            skill=self.skill, cefr_level="A2", difficulty_score=0.5,
            question_type="multiple_choice", question="?", correct_answer="a",
        )

    def test_baseline_when_no_attempts(self):
        self.assertEqual(learning_speed_for(self.user), 1.0)

    def test_fast_user_above_one(self):
        for _ in range(5):
            ExerciseAttempt.objects.create(
                user=self.user, exercise=self.ex,
                user_answer="a", is_correct=True, score=1.0,
                time_spent_seconds=10,
            )
        self.assertGreater(learning_speed_for(self.user), 1.5)

    def test_slow_user_below_one(self):
        for _ in range(5):
            ExerciseAttempt.objects.create(
                user=self.user, exercise=self.ex,
                user_answer="a", is_correct=True, score=1.0,
                time_spent_seconds=120,
            )
        self.assertLess(learning_speed_for(self.user), 0.5)


class PersistTests(TestCase):
    def test_writes_metadata_and_speed_field(self):
        user = User.objects.create_user(username="p@x.com", email="p@x.com", password="pw")
        StudentLearningProfile.objects.create(user=user)
        result = persist_for_user(user)
        self.assertIn("engagement_score", result)
        self.assertIn("churn_risk", result)
        self.assertIn("learning_speed", result)
        prof = StudentLearningProfile.objects.get(user=user)
        self.assertEqual(prof.metadata.get("behavior", {}).get("churn_risk"), result["churn_risk"])
        self.assertEqual(prof.learning_speed, result["learning_speed"])


class ImprovementTrendTests(TestCase):
    def test_returns_dense_series(self):
        user = User.objects.create_user(username="tr@x.com", email="tr@x.com", password="pw")
        today = timezone.localdate()
        LearnerActivitySnapshot.objects.create(
            user=user, date=today - timedelta(days=2),
            theta_score=0.2, quiz_accuracy=70.0,
        )
        LearnerActivitySnapshot.objects.create(
            user=user, date=today, theta_score=0.5, quiz_accuracy=82.0,
        )
        trend = improvement_trend(user, days=4)
        self.assertEqual(len(trend), 4)
        self.assertEqual(trend[-1]["accuracy"], 82.0)
