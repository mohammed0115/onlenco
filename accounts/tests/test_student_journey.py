"""End-to-end contracts for the student journey:
register → verify → onboarding → placement → dashboard → lesson.

These tests pin the rules in ``accounts.onboarding`` and the lesson
detail view's resilience so a brand-new student can reach a lesson
without ever being forced into an infinite onboarding/placement loop
and without seeing a 500.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone


User = get_user_model()


def _verified_student(email: str = "j@example.com"):
    """Return a user whose email is verified but onboarding not done."""
    u = User.objects.create_user(username=email, email=email, password="pw")
    u.profile.email_verified = True
    u.profile.save()
    return u


@override_settings(AXES_ENABLED=False)
class OnboardingStateContractTests(TestCase):
    """``next_url_for`` is the single source of truth for the journey."""

    def test_new_verified_student_goes_to_onboarding_choice(self):
        from accounts.onboarding import next_url_for
        u = _verified_student("new@x.com")
        url = next_url_for(u)
        self.assertEqual(url, reverse("onboarding_choice"))

    def test_beginner_choice_marks_onboarding_completed(self):
        from accounts.onboarding import (
            complete_beginner_onboarding,
            next_url_for,
        )
        u = _verified_student("beg@x.com")
        complete_beginner_onboarding(u)
        u.profile.refresh_from_db()
        self.assertTrue(u.profile.onboarding_completed)
        self.assertEqual(u.profile.onboarding_path, "beginner_start")
        self.assertEqual(u.profile.cefr_level, "A0")
        self.assertEqual(u.profile.initial_cefr_level, "A0")
        # And next_url_for clears — no more onboarding redirect.
        self.assertIsNone(next_url_for(u))

    def test_placement_completed_student_goes_to_dashboard(self):
        from accounts.onboarding import (
            complete_placement_onboarding,
            next_url_for,
        )
        u = _verified_student("pl@x.com")
        # Set the fields the placement view normally writes before
        # delegating to onboarding helper.
        u.profile.cefr_level = "B1"
        u.profile.placement_completed = True
        u.profile.save()
        complete_placement_onboarding(u.profile, level="B1")
        u.profile.refresh_from_db()
        self.assertTrue(u.profile.onboarding_completed)
        self.assertEqual(u.profile.onboarding_path, "placement_test")
        self.assertEqual(u.profile.initial_cefr_level, "B1")
        # The user is "done" — next_url_for returns None.
        self.assertIsNone(next_url_for(u))

    def test_completed_student_does_not_see_required_placement_again(self):
        """A student who finished onboarding (either path) must never be
        forced back to onboarding/placement on subsequent logins."""
        from accounts.onboarding import (
            complete_beginner_onboarding,
            next_url_for,
        )
        u = _verified_student("returning@x.com")
        complete_beginner_onboarding(u)
        # Simulate a later login — call next_url_for again.
        self.assertIsNone(next_url_for(u))

    def test_retake_placement_is_optional_not_forced(self):
        """The retake URL exists (so the dashboard can offer a button)
        but completed users hit ``next_url_for`` and get None back."""
        from accounts.onboarding import next_url_for
        u = _verified_student("retake@x.com")
        u.profile.onboarding_completed = True
        u.profile.onboarding_path = "placement_test"
        u.profile.placement_completed = True
        u.profile.cefr_level = "A2"
        u.profile.initial_cefr_level = "A2"
        u.profile.onboarding_completed_at = timezone.now()
        u.profile.save()
        # No forced redirect.
        self.assertIsNone(next_url_for(u))
        # Retake URL resolves.
        self.assertTrue(reverse("placement_retake"))


@override_settings(AXES_ENABLED=False)
class LessonDetailResilienceTests(TestCase):
    """The lesson detail page must never 500 — every failure mode has
    a defined alternate response (302 / 403 / 404)."""

    def setUp(self):
        from courses.models import Course, CourseLevel, Lesson, CourseUnit
        self.user = User.objects.create_user(
            username="lr@x.com", email="lr@x.com", password="pw",
        )
        self.user.profile.email_verified = True
        self.user.profile.subscription_status = "active"
        self.user.profile.subscription_expires_at = (
            timezone.now() + timezone.timedelta(days=30)
        )
        self.user.profile.cefr_level = "A0"
        self.user.profile.initial_cefr_level = "A0"
        self.user.profile.placement_completed = True
        self.user.profile.onboarding_completed = True
        self.user.profile.onboarding_path = "beginner_start"
        self.user.profile.save()

        level, _ = CourseLevel.objects.get_or_create(
            code="A0", defaults={"name": "Beginner", "order": 1},
        )
        self.course = Course.objects.create(
            title="A0 Test Course",
            level=level,
            status="published",
            language="en",
        )
        self.unit = CourseUnit.objects.create(
            course=self.course, title="Unit 1", order=1, is_published=True,
        )
        self.lesson = Lesson.objects.create(
            course=self.course, unit=self.unit, title="Lesson 1",
            status="published", order=1, is_active=True,
            lesson_type="reading",
        )
        self.client.force_login(self.user)

    def _url(self):
        return reverse(
            "courses:lesson_detail",
            kwargs={"course_pk": self.course.pk, "lesson_pk": self.lesson.pk},
        )

    def test_lesson_detail_returns_200_for_accessible_lesson(self):
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)

    def test_lesson_detail_handles_missing_quiz_without_500(self):
        # No LessonQuiz attached — the view's try/except must swallow.
        self.assertFalse(hasattr(self.lesson, "quiz") and getattr(self.lesson, "quiz", None))
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)

    def test_lesson_detail_handles_missing_video_without_500(self):
        self.lesson.video_file = ""
        self.lesson.video_url = ""
        self.lesson.save()
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)

    def test_lesson_detail_creates_progress_safely(self):
        from courses.models import CourseLessonProgress
        self.assertFalse(CourseLessonProgress.objects.filter(
            user=self.user, lesson=self.lesson,
        ).exists())
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, 200)
        # Progress row created on first access.
        self.assertTrue(CourseLessonProgress.objects.filter(
            user=self.user, lesson=self.lesson,
        ).exists())

    def test_locked_lesson_returns_clear_response_not_500(self):
        """Unsubscribed user hitting a paid lesson must get 403 (clear),
        never 500."""
        self.user.profile.subscription_status = "inactive"
        self.user.profile.subscription_expires_at = None
        self.user.profile.onboarding_completed_at = (
            timezone.now() - timezone.timedelta(days=400)
        )
        self.user.profile.save()
        r = self.client.get(self._url())
        # 403 or 302 (redirect) — anything but 500 is the contract.
        self.assertIn(r.status_code, (302, 403))
        self.assertNotEqual(r.status_code, 500)


@override_settings(AXES_ENABLED=False)
class FullJourneyE2ETests(TestCase):
    """End-to-end happy paths."""

    def test_full_beginner_onboarding_to_first_lesson(self):
        """register → verify → choose beginner → reach dashboard 200 →
        reach a lesson 200."""
        from accounts.onboarding import (
            complete_beginner_onboarding, next_url_for,
        )
        from courses.models import Course, CourseLevel, Lesson, CourseUnit
        u = _verified_student("e2e_beg@x.com")
        # Active subscription so the lesson page paywall doesn't bounce.
        u.profile.subscription_status = "active"
        u.profile.subscription_expires_at = (
            timezone.now() + timezone.timedelta(days=30)
        )
        u.profile.save()
        complete_beginner_onboarding(u)
        u.refresh_from_db()
        self.assertIsNone(next_url_for(u))

        level, _ = CourseLevel.objects.get_or_create(
            code="A0", defaults={"name": "Beginner", "order": 1},
        )
        course = Course.objects.create(
            title="A0 Demo", level=level, status="published", language="en",
        )
        unit = CourseUnit.objects.create(
            course=course, title="Unit 1", order=1, is_published=True,
        )
        lesson = Lesson.objects.create(
            course=course, unit=unit, title="L1", status="published",
            order=1, is_active=True, lesson_type="reading",
        )

        self.client.force_login(u)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        r = self.client.get(reverse(
            "courses:lesson_detail",
            kwargs={"course_pk": course.pk, "lesson_pk": lesson.pk},
        ))
        self.assertEqual(r.status_code, 200)

    def test_completed_placement_not_repeated_after_login(self):
        """A student who finished placement should NOT see any forced
        placement redirect on subsequent dashboard visits."""
        from accounts.onboarding import (
            complete_placement_onboarding, next_url_for,
        )
        u = _verified_student("e2e_pl@x.com")
        u.profile.subscription_status = "active"
        u.profile.subscription_expires_at = (
            timezone.now() + timezone.timedelta(days=30)
        )
        u.profile.cefr_level = "B1"
        u.profile.placement_completed = True
        u.profile.save()
        complete_placement_onboarding(u.profile, level="B1")

        # "Logout & login later" simulated by refetching the user.
        u.refresh_from_db()
        self.assertIsNone(next_url_for(u))

        self.client.force_login(u)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
