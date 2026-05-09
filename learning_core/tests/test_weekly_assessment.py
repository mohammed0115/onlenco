from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from learning_core.models import LearningRecommendation, WeeklyAssessment
from learning_core.services.weekly_assessment import (
    LESSONS_PER_ASSESSMENT,
    complete,
    maybe_trigger,
)
from lessons.models import Lesson, LessonProgress

User = get_user_model()


class WeeklyAssessmentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="wa", password="pw")
        self.lessons = [
            Lesson.objects.create(
                title=f"L{i}", skill="reading", level="A2", duration_minutes=10
            )
            for i in range(LESSONS_PER_ASSESSMENT + 1)
        ]

    def _complete_n(self, n: int):
        for i in range(n):
            LessonProgress.objects.create(
                user=self.user,
                lesson=self.lessons[i],
                video_completed=True,
                quiz_passed=True,
                completed_at=timezone.now(),
            )

    def test_no_trigger_below_threshold(self):
        self._complete_n(LESSONS_PER_ASSESSMENT - 1)
        self.assertIsNone(maybe_trigger(self.user))

    def test_trigger_at_threshold(self):
        self._complete_n(LESSONS_PER_ASSESSMENT)
        wa = maybe_trigger(self.user)
        self.assertIsNotNone(wa)
        self.assertEqual(wa.status, "pending")
        self.assertEqual(wa.triggered_after_lessons_count, LESSONS_PER_ASSESSMENT)
        # A recommendation surfaces it
        self.assertTrue(
            LearningRecommendation.objects.filter(
                user=self.user, recommendation_type="weekly_assessment"
            ).exists()
        )

    def test_idempotent_at_same_threshold(self):
        self._complete_n(LESSONS_PER_ASSESSMENT)
        wa = maybe_trigger(self.user)
        self.assertIsNotNone(wa)
        again = maybe_trigger(self.user)
        self.assertIsNone(again)
        self.assertEqual(WeeklyAssessment.objects.filter(user=self.user).count(), 1)

    def test_complete_records_score_and_status(self):
        self._complete_n(LESSONS_PER_ASSESSMENT)
        wa = maybe_trigger(self.user)
        complete(wa, score=87.5)
        wa.refresh_from_db()
        self.assertEqual(wa.status, "completed")
        self.assertEqual(wa.score, 87.5)
        self.assertIsNotNone(wa.completed_at)

    def test_trigger_sends_email_to_student(self):
        from django.core import mail

        self.user.email = "stud@example.com"
        self.user.save(update_fields=["email"])
        # Force English so we can match the subject string deterministically.
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])
        self._complete_n(LESSONS_PER_ASSESSMENT)
        maybe_trigger(self.user)
        # maybe_trigger also generates exercises → exercises_generated email fires too.
        self.assertGreaterEqual(len(mail.outbox), 1)
        weekly = next(
            (m for m in mail.outbox if "weekly assessment" in m.subject.lower()),
            None,
        )
        self.assertIsNotNone(weekly, "weekly_assessment_available email not sent")
        self.assertIn("stud@example.com", weekly.to)
        self.assertIn("/dashboard/weekly/", weekly.body)

    def test_trigger_skips_email_for_user_without_email(self):
        from django.core import mail

        self._complete_n(LESSONS_PER_ASSESSMENT)
        maybe_trigger(self.user)
        self.assertEqual(len(mail.outbox), 0)
