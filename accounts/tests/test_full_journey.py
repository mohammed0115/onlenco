"""End-to-end student-journey tests.

These walk the full chain — register → verify-email → onboarding choice
→ first lesson — for both onboarding paths, asserting the redirect rule
holds at every step. They catch regressions that *individual unit tests*
would miss because each step in isolation could pass while the chain
breaks (e.g. a redirect URL silently changing).

Both `assess()` and `build_diagnostic_profile` are mocked so the tests
don't depend on AI services or the diagnostic engine's full behaviour."""
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts import onboarding as onboarding_lib
from courses.models import Course, CourseLevel, Lesson as CourseLesson
from learning_core.models import LearningRecommendation, StudentLearningProfile
from lessons.models import Lesson, LessonProgress

User = get_user_model()


def _make_verified_user(email="journey@x.com", password="pw"):
    user = User.objects.create_user(username=email, email=email, password=password)
    user.profile.email_verified = True
    user.profile.preferred_language = "en"
    user.profile.save(update_fields=["email_verified", "preferred_language"])
    return user


@override_settings(AXES_ENABLED=False)
class BeginnerJourneyTests(TestCase):
    """Scenario B from the spec — the full beginner path."""

    @classmethod
    def setUpTestData(cls):
        # Legacy lessons remain for compatibility tests.
        cls.first_lesson = Lesson.objects.create(
            title="A0 Hello", skill="grammar", level="A0", sort_order=1,
        )
        cls.second_lesson = Lesson.objects.create(
            title="A1 Greetings", skill="grammar", level="A1", sort_order=10,
        )
        # The student dashboard learning path is backed by the courses app.
        level = CourseLevel.objects.create(code="A0", name="A0", order=0)
        cls.course = Course.objects.create(
            title="A0 Starter Course",
            slug="a0-starter-course",
            level=level,
            status="published",
            is_active=True,
            is_free=True,
        )
        cls.course_lesson = CourseLesson.objects.create(
            course=cls.course,
            title="A0 Course Hello",
            status="published",
            is_active=True,
        )

    def test_full_beginner_journey_register_to_first_lesson(self):
        user = _make_verified_user()

        # 1. Login → next_url_for says: go to onboarding.
        self.client.force_login(user)
        self.assertEqual(
            onboarding_lib.next_url_for(user),
            reverse("onboarding_choice"),
        )

        # 2. The onboarding page renders.
        resp = self.client.get(reverse("onboarding_choice"))
        self.assertEqual(resp.status_code, 200)

        # 3. Pick "Start From Beginner".
        resp = self.client.post(reverse("onboarding_beginner"))
        self.assertRedirects(resp, reverse("dashboard"),
                             fetch_redirect_response=False)

        # 4. The side-effects fired.
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.cefr_level, "A0")
        self.assertEqual(user.profile.onboarding_path, "beginner_start")
        self.assertTrue(user.profile.onboarding_completed)

        # 5. StudentLearningProfile exists.
        self.assertTrue(
            StudentLearningProfile.objects.filter(user=user).exists()
        )

        # 6. Starter recommendation seeded.
        self.assertTrue(
            LearningRecommendation.objects.filter(
                user=user, recommendation_type="continue_lesson",
            ).exists()
        )

        # 7. Dashboard shows the courses-backed recommendation card.
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "data-testid=\"recommended-course-hero\"")
        self.assertContains(resp, "A0 Starter Course")
        self.assertContains(resp, "A0 Course Hello")

    def test_dashboard_no_beginner_hero_after_first_lesson_attempted(self):
        user = _make_verified_user()
        onboarding_lib.complete_beginner_onboarding(user)

        # As soon as the student opens the lesson (creating a
        # LessonProgress row), the "your first lesson" hero must
        # disappear — they're past the hand-hold.
        LessonProgress.objects.create(user=user, lesson=self.first_lesson)
        self.client.force_login(user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "data-testid=\"beginner-first-lesson-hero\"")

    def test_beginner_completes_first_lesson_and_earns_xp(self):
        """Regression test for the audit's Critical Gap #2:
        register → onboarding → courses-app lesson complete → XP credited.

        Verifies the free-tier window lets a non-subscribed beginner
        through, the courses-app lesson has a completion endpoint, and
        the motivation engine fires inline so XP appears immediately.
        """
        from courses.models import CourseLessonProgress
        from motivation.models import LearnerActivitySnapshot, UserXP

        user = _make_verified_user(email="xp_beginner@x.com")
        self.client.force_login(user)
        # Step through onboarding (sets onboarding_completed_at → grants
        # the 7-day free trial via Profile.is_in_free_tier).
        resp = self.client.post(reverse("onboarding_beginner"))
        self.assertRedirects(resp, reverse("dashboard"),
                             fetch_redirect_response=False)
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.is_subscribed)
        self.assertTrue(user.profile.is_in_free_tier,
                        "Free trial must be active right after onboarding")

        # Hit the completion endpoint on the courses-app lesson.
        resp = self.client.post(
            reverse("courses:mark_lesson_complete",
                    args=[self.course.pk, self.course_lesson.pk]),
        )
        # Free-tier should let the un-subscribed user through (302 to
        # lesson_detail, NOT 403).
        self.assertEqual(resp.status_code, 302)
        progress = CourseLessonProgress.objects.get(
            user=user, lesson=self.course_lesson,
        )
        self.assertTrue(progress.video_completed)
        # No quiz on this seed lesson → completed_at set immediately.
        self.assertIsNotNone(progress.completed_at)

        # Motivation engine ran inline: today's snapshot counts the lesson,
        # and XP was credited.
        from django.utils import timezone
        snap = LearnerActivitySnapshot.objects.filter(
            user=user, date=timezone.localdate(),
        ).first()
        self.assertIsNotNone(snap, "LearnerActivitySnapshot must exist for today")
        self.assertGreaterEqual(snap.lessons_completed, 1)
        xp = UserXP.objects.filter(user=user).first()
        self.assertIsNotNone(xp, "UserXP row must exist")
        self.assertGreater(xp.total_xp, 0,
                           "XP must be awarded for completing the first lesson")


@override_settings(AXES_ENABLED=False)
class PlacementJourneyTests(TestCase):
    """Scenario A from the spec — the full placement path."""

    def setUp(self):
        Lesson.objects.create(title="A1 lesson", skill="grammar",
                              level="A1", sort_order=1)

    def test_full_placement_journey_register_to_dashboard(self):
        user = _make_verified_user(email="pj@x.com")

        # 1. Login → onboarding choice.
        self.client.force_login(user)
        self.assertEqual(
            onboarding_lib.next_url_for(user),
            reverse("onboarding_choice"),
        )

        # 2. Pick the placement card → redirects to the new dynamic flow.
        resp = self.client.post(reverse("onboarding_placement"))
        self.assertRedirects(resp, reverse("placement_start"),
                             fetch_redirect_response=False)

        # 3. Take the test through the CURATED dynamic flow (the legacy
        # single-page placement is retired). Start → written MCQ from the
        # active bank → speaking (scored via the dynamic scorer, AI mocked).
        from io import StringIO
        from django.core.management import call_command
        from placement.models import PlacementAttempt
        from placement.services.answer_key import correct_answer_for
        call_command("seed_placement_questions", stdout=StringIO())

        self.client.get(reverse("placement_start"))
        attempt = PlacementAttempt.objects.get(user=user)

        wq = list(attempt.questions.filter(section="written").select_related("question"))
        wdata = {
            f"q_{aq.id}": correct_answer_for(
                options=aq.question.options, rubric=aq.question.scoring_rubric,
                expected_type=aq.question.expected_answer_type,
            )
            for aq in wq
        }
        self.client.post(reverse("placement_written", args=[attempt.id]), wdata)

        fake_assess = {
            "level": "B1", "written_score": 78, "speaking_score": 70,
            "feedback": "Solid grammar; expand vocabulary range.",
        }
        sq = list(attempt.questions.filter(section="speaking"))
        sdata = {
            f"q_{aq.id}_transcript": "I enjoy reading and learning English every day."
            for aq in sq
        }
        with patch("placement.views.assess", return_value=fake_assess), \
             patch("placement.views.build_diagnostic_profile", return_value={}):
            resp = self.client.post(
                reverse("placement_speaking", args=[attempt.id]), sdata, follow=True,
            )
        self.assertEqual(resp.status_code, 200)

        # 4. Profile carries an assigned level + onboarding state.
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.cefr_level)
        self.assertTrue(user.profile.placement_completed)
        self.assertTrue(user.profile.onboarding_completed)
        self.assertEqual(user.profile.onboarding_path, "placement_test")
        self.assertTrue(user.profile.initial_cefr_level)

        # 5. The result page is NOT a dead-end — it carries a link
        # back to the dashboard. (#27 lock-in test.)
        self.assertContains(resp, reverse("dashboard"))

        # 6. Logging in again does NOT bring the onboarding page back.
        self.assertIsNone(onboarding_lib.next_url_for(user))

        # 7. Dashboard renders successfully for the placed user.
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        # And the beginner hero is NOT present (this is a placed user).
        self.assertNotContains(resp, "data-testid=\"beginner-first-lesson-hero\"")

    def test_starting_placement_does_not_complete_onboarding(self):
        """Merely entering the placement flow must NOT half-complete
        onboarding — it only finalises once the test is submitted."""
        from io import StringIO
        from django.core.management import call_command
        call_command("seed_placement_questions", stdout=StringIO())
        user = _make_verified_user(email="pj-fail@x.com")
        self.client.force_login(user)

        # Legacy entry redirects into the curated flow; starting it creates
        # an attempt but leaves onboarding pending.
        resp = self.client.get(reverse("placement"))
        self.assertRedirects(resp, reverse("placement_start"),
                             fetch_redirect_response=False)
        self.client.get(reverse("placement_start"))
        user.profile.refresh_from_db()
        self.assertFalse(user.profile.onboarding_completed)
        self.assertFalse(user.profile.placement_completed)
        self.assertEqual(
            onboarding_lib.next_url_for(user),
            reverse("onboarding_choice"),
        )


@override_settings(AXES_ENABLED=False)
class StarterRecommendationTests(TestCase):
    """Lock down the rule that beginner onboarding seeds exactly one
    starter recommendation, and only when the user has none yet."""

    def test_complete_beginner_onboarding_seeds_recommendation(self):
        user = _make_verified_user(email="rec@x.com")
        onboarding_lib.complete_beginner_onboarding(user)
        recs = list(LearningRecommendation.objects.filter(user=user))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].recommendation_type, "continue_lesson")
        self.assertEqual(recs[0].metadata.get("source"), "beginner_onboarding")

    def test_starter_recommendation_is_idempotent(self):
        user = _make_verified_user(email="rec-idem@x.com")
        onboarding_lib.complete_beginner_onboarding(user)
        onboarding_lib.complete_beginner_onboarding(user)
        self.assertEqual(
            LearningRecommendation.objects.filter(user=user).count(),
            1,
        )

    def test_starter_skipped_when_existing_recommendation_present(self):
        """If the diagnostic engine already produced recommendations
        (e.g. user retook placement before flipping to beginner), don't
        clobber its richer output with the starter card."""
        user = _make_verified_user(email="rec-existing@x.com")
        LearningRecommendation.objects.create(
            user=user, recommendation_type="practice_skill",
            title="Practice past simple", priority=80.0,
        )
        onboarding_lib.complete_beginner_onboarding(user)
        # Still only the original recommendation.
        recs = list(LearningRecommendation.objects.filter(user=user))
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].recommendation_type, "practice_skill")
