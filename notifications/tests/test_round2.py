"""Tests for the second round of notification wiring."""
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from notifications import constants as C
from notifications.models import EmailNotification, NotificationEvent

User = get_user_model()


@override_settings(AI_API_KEY="")
class StubbedEventTriggerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", email="u@x", password="pw")

    def test_placement_completed_sent(self):
        from placement.services.diagnostic_engine import build_diagnostic_profile

        canned = {"level": "B1", "written_score": 60, "speaking_score": 50, "feedback": "ok"}
        build_diagnostic_profile(self.user, {"q1": "x", "q3": "yes", "q4": "ok"}, assessment=canned)
        ev = NotificationEvent.objects.filter(
            event_type=C.PLACEMENT_COMPLETED, user=self.user
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(len(mail.outbox), 1)

    def test_lesson_completed_sent_when_progress_completes(self):
        from lessons.models import Lesson, LessonProgress, Question, Quiz
        from lessons.services.adaptive_quiz_adapter import process_quiz_submission
        from django.utils import timezone

        lesson = Lesson.objects.create(
            title="L1", skill="reading", level="A2", duration_minutes=10
        )
        quiz = Quiz.objects.create(lesson=lesson, pass_score=50)
        q1 = Question.objects.create(
            quiz=quiz, prompt="?", choice_a="a", choice_b="b", correct="a"
        )
        # Mark video complete + create progress with completed_at
        LessonProgress.objects.create(
            user=self.user, lesson=lesson, video_completed=True,
            quiz_passed=True, completed_at=timezone.now(),
        )
        process_quiz_submission(self.user, lesson, [{"q": q1, "chosen": "a", "correct": "a"}])
        self.assertTrue(
            NotificationEvent.objects.filter(
                event_type=C.LESSON_COMPLETED, user=self.user
            ).exists()
        )

    def test_weakness_detected_sent_for_newly_active(self):
        from learning_core.models import GrammarTopic, Skill, UserError
        from learning_core.services.weakness_engine import update_user_weaknesses

        skill = Skill.objects.create(name="Gram", category="grammar", cefr_level="A2")
        topic = GrammarTopic.objects.create(name="Past Simple", slug="past-simple", cefr_level="A2")
        for _ in range(5):
            UserError.objects.create(
                user=self.user, source_type="quiz", error_type="grammar",
                skill=skill, grammar_topic=topic, severity=8,
            )
        update_user_weaknesses(self.user)
        self.assertTrue(
            NotificationEvent.objects.filter(
                event_type=C.WEAKNESS_DETECTED, user=self.user
            ).exists()
        )

    def test_exercises_generated_sent(self):
        from learning_core.services.exercise_generator import generate_personalized_exercises

        generate_personalized_exercises(self.user, count_per_weakness=1)
        self.assertTrue(
            NotificationEvent.objects.filter(
                event_type=C.EXERCISES_GENERATED, user=self.user
            ).exists()
        )

    def test_level_improved_sent_on_upward_transition(self):
        from learning_core.models import AdaptiveExercise, ExerciseAttempt, StudentLearningProfile
        from learning_core.services.adaptive_difficulty import update_theta

        profile = StudentLearningProfile.objects.create(
            user=self.user, current_cefr_level="A1", theta_score=-1.6,
        )
        ex = AdaptiveExercise.objects.create(
            cefr_level="A2", difficulty_score=0.1, question_type="multiple_choice",
            question="x", options=["a"], correct_answer="a",
        )
        # Big positive update to push above the A2 threshold
        for _ in range(50):
            attempt = ExerciseAttempt.objects.create(
                user=self.user, exercise=ex, is_correct=True, score=1.0,
            )
            update_theta(self.user, ex, attempt, alpha=1.0)
        self.assertTrue(
            NotificationEvent.objects.filter(
                event_type=C.LEVEL_IMPROVED, user=self.user
            ).exists()
        )

    def test_weekly_assessment_result_sent_on_complete(self):
        from learning_core.models import WeeklyAssessment
        from learning_core.services.weekly_assessment import complete

        wa = WeeklyAssessment.objects.create(
            user=self.user, triggered_after_lessons_count=3, status="in_progress"
        )
        complete(wa, score=80.0)
        self.assertTrue(
            NotificationEvent.objects.filter(
                event_type=C.WEEKLY_ASSESSMENT_RESULT, user=self.user
            ).exists()
        )

    def test_ai_usage_high_alerts_admin_at_80pct(self):
        from core.services.ai_usage import DAILY_LIMITS, is_within_limit, log_usage
        admin = User.objects.create_user(username="adm", email="adm@x", password="pw", is_staff=True)
        free, _ = DAILY_LIMITS["tutor"]
        threshold = int(free * 0.8)
        for _ in range(threshold):
            log_usage(self.user, "tutor")
        # The next is_within_limit call should be the trigger
        is_within_limit(self.user, "tutor")
        self.assertTrue(
            NotificationEvent.objects.filter(event_type=C.AI_USAGE_HIGH).exists()
        )


class EmailVerificationTests(TestCase):
    def test_token_issued_and_consumed(self):
        from notifications.models import EmailVerificationToken
        from notifications.services import consume_verification_token, issue_verification_token

        u = User.objects.create_user(username="ev", email="ev@x", password="pw")
        token = issue_verification_token(u)
        self.assertIsNotNone(token)
        self.assertEqual(EmailVerificationToken.objects.filter(user=u).count(), 1)
        self.assertTrue(consume_verification_token(token.token))
        token.refresh_from_db()
        self.assertIsNotNone(token.used_at)
        u.profile.refresh_from_db()
        self.assertTrue(u.profile.email_verified)

    def test_verify_view_redirects_to_auth(self):
        from notifications.services import issue_verification_token

        u = User.objects.create_user(username="ev2", email="ev2@x", password="pw")
        token = issue_verification_token(u)
        r = self.client.get(reverse("verify_email", args=[token.token]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, "/auth/")

    def test_verify_invalid_token_redirects(self):
        r = self.client.get(reverse("verify_email", args=["bogus"]))
        self.assertEqual(r.status_code, 302)


class PreferencesApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pa", email="pa@x", password="pw")
        self.client.force_login(self.user)

    def test_get_creates_default_preferences(self):
        r = self.client.get("/api/v1/notifications/preferences/")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["learning_updates"])
        self.assertEqual(body["language"], "en")

    def test_patch_updates_preferences(self):
        r = self.client.patch(
            "/api/v1/notifications/preferences/",
            data={"learning_updates": False, "language": "ar"},
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["learning_updates"])
        self.assertEqual(r.json()["language"], "ar")

    def test_anonymous_blocked(self):
        self.client.logout()
        r = self.client.get("/api/v1/notifications/preferences/")
        self.assertIn(r.status_code, (401, 403))


class UnsubscribeTests(TestCase):
    def test_unsubscribe_link_disables_optional_emails(self):
        from notifications.models import NotificationPreference
        from notifications.views import make_unsubscribe_token

        u = User.objects.create_user(username="us", email="us@x", password="pw")
        token = make_unsubscribe_token(u)

        r = self.client.get(f"/notifications/unsubscribe/{token}/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Unsubscribe")
        # POST confirms
        r2 = self.client.post(f"/notifications/unsubscribe/{token}/")
        self.assertEqual(r2.status_code, 200)
        pref = NotificationPreference.objects.get(user=u)
        self.assertFalse(pref.learning_updates)
        self.assertFalse(pref.payment_updates)
        self.assertFalse(pref.marketing_emails)

    def test_invalid_token_400(self):
        r = self.client.get("/notifications/unsubscribe/invalid/")
        self.assertEqual(r.status_code, 400)


class RetryBackoffTests(TestCase):
    def test_max_attempts_caps_retries(self):
        from unittest.mock import patch
        from notifications.services.email_service import EmailMultiAlternatives
        from notifications.services.notification_service import (
            MAX_ATTEMPTS,
            NotificationService,
        )

        u = User.objects.create_user(username="r", email="r@x", password="pw")
        # Force 1 initial failure
        with patch.object(EmailMultiAlternatives, "send", side_effect=RuntimeError("x")):
            ev = NotificationService().trigger(C.USER_REGISTERED, user=u)
        en = EmailNotification.objects.get(event=ev)
        self.assertEqual(en.status, C.STATUS_FAILED)
        self.assertEqual(en.attempts_count, 1)

        # Drive attempts up to MAX with patched failure
        svc = NotificationService()
        with patch.object(EmailMultiAlternatives, "send", side_effect=RuntimeError("x")):
            for _ in range(MAX_ATTEMPTS + 2):
                svc.retry_failed_email(en)
                en.refresh_from_db()
        self.assertLessEqual(en.attempts_count, MAX_ATTEMPTS)
        self.assertIn("max attempts", en.error_message)


class ManagementCommandTests(TestCase):
    def test_send_subscription_expiring_runs_cleanly(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("send_subscription_expiring", "--days", "3", stdout=out)
        self.assertIn("subscription_expiring", out.getvalue())

    def test_send_inactive_reminders_runs_cleanly(self):
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("send_inactive_reminders", "--days", "14", stdout=out)
        self.assertIn("inactive_student_reminder", out.getvalue())

    def test_send_admin_digests_runs_cleanly(self):
        from django.core.management import call_command
        from io import StringIO

        admin = User.objects.create_user(
            username="dadm", email="dadm@x", password="pw", is_staff=True
        )
        out = StringIO()
        call_command("send_admin_digests", "--window", "all", stdout=out)
        self.assertIn("daily admin", out.getvalue().lower())
        # Admin received at least one summary email
        self.assertTrue(
            EmailNotification.objects.filter(
                recipient_email="dadm@x", status=C.STATUS_SENT
            ).exists()
        )
