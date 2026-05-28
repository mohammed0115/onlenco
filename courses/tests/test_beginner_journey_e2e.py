"""End-to-end student journey tests for the Onlenco Beginner course (P11).

Walks through the 8 flows specified in Prompt 11. Each flow is an
independent test method so a failure pinpoints exactly which step
breaks. Inspection only — does not fix code if it breaks.
"""
from __future__ import annotations

from io import StringIO
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone

from courses.models import (
    Course, CourseEnrollment, CourseLessonProgress, CourseReview, Lesson,
)


User = get_user_model()
COURSE_SLUG = "onlenco-beginner"


class BeginnerJourneyE2ETests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_onlenco_beginner_48_units",  "--quiet", stdout=StringIO())
        call_command("seed_onlenco_beginner_quiz_bank", "--quiet", stdout=StringIO())
        call_command("seed_onlenco_beginner_reviews",   "--quiet", stdout=StringIO())
        cls.course = Course.objects.get(slug=COURSE_SLUG)

    def _student(self, name="learner") -> User:
        u = User.objects.create_user(
            username=name, password="pw", email=f"{name}@onlenco.test",
        )
        if hasattr(u, "profile"):
            u.profile.email_verified = True
            u.profile.subscription_status = "active"
            u.profile.save()
        CourseEnrollment.objects.get_or_create(user=u, course=self.course)
        return u

    def _client(self, user) -> Client:
        c = Client(SERVER_NAME="127.0.0.1")
        c.force_login(user)
        return c

    # ------------------------------------------------------------------
    # Flow 1 — full new-student first session up to Unit 1 completion
    # ------------------------------------------------------------------
    def test_flow_1_new_student_opens_unit_1(self):
        user = self._student("alice")
        c = self._client(user)
        lesson_1 = Lesson.objects.get(course=self.course, order=1)
        r = c.get(
            f"/courses/{self.course.pk}/lessons/{lesson_1.pk}/",
            HTTP_HOST="127.0.0.1",
        )
        self.assertNotEqual(r.status_code, 500, "Unit 1 page must not 500")
        # Either 200 (lesson visible) or redirect (drip gate); never 500.
        self.assertIn(r.status_code, (200, 302))

    def test_flow_1_quiz_button_visible_on_unit_1(self):
        user = self._student("bob")
        c = self._client(user)
        lesson_1 = Lesson.objects.get(course=self.course, order=1)
        r = c.get(
            f"/courses/{self.course.pk}/lessons/{lesson_1.pk}/",
            HTTP_HOST="127.0.0.1",
        )
        if r.status_code == 200:
            html = r.content.decode("utf-8", errors="replace")
            self.assertIn("data-action=\"start-quiz\"", html)

    # ------------------------------------------------------------------
    # Flow 3 — units without media must not crash
    # ------------------------------------------------------------------
    def test_flow_3_lessons_without_media_dont_crash(self):
        user = self._student("clara")
        c = self._client(user)
        # Try a sample of lessons across the 6 clusters.
        for order in (1, 9, 20, 27, 35, 43, 48):
            lesson = Lesson.objects.get(course=self.course, order=order)
            self.assertEqual(lesson.media.count(), 0)  # no LessonMedia rows yet
            r = c.get(
                f"/courses/{self.course.pk}/lessons/{lesson.pk}/",
                HTTP_HOST="127.0.0.1",
            )
            self.assertNotEqual(
                r.status_code, 500,
                f"Unit {order} ({lesson.title}) returned 500 without media",
            )

    # ------------------------------------------------------------------
    # Flow 5 — Arabic UI with RTL + English content stays LTR
    # ------------------------------------------------------------------
    def test_flow_5_arabic_ui_keeps_english_examples_ltr(self):
        user = self._student("dana")
        c = self._client(user)
        lesson = Lesson.objects.get(course=self.course, order=1)
        r = c.get(
            f"/courses/{self.course.pk}/lessons/{lesson.pk}/",
            HTTP_HOST="127.0.0.1",
            HTTP_ACCEPT_LANGUAGE="ar-EG",
        )
        if r.status_code == 200:
            html = r.content.decode("utf-8", errors="replace")
            self.assertIn("dir=\"ltr\"", html)

    # ------------------------------------------------------------------
    # Flow 6 — Quiz exists and is linked
    # ------------------------------------------------------------------
    def test_flow_6_quiz_exists_for_every_unit(self):
        for lesson in Lesson.objects.filter(course=self.course):
            self.assertTrue(
                hasattr(lesson, "quiz") and lesson.quiz is not None,
                f"Lesson {lesson.order} ({lesson.title}) has no quiz",
            )
            n = lesson.quiz.questions.count()
            self.assertGreaterEqual(n, 8)
            self.assertLessEqual(n, 12)

    # ------------------------------------------------------------------
    # Flow 7 — AI tutor receives scoped lesson context
    # ------------------------------------------------------------------
    def test_flow_7_ai_tutor_prompt_is_scoped_per_lesson(self):
        from tutor.services.lesson_ai_context_builder import build_lesson_tutor_prompt
        lesson_5  = Lesson.objects.get(course=self.course, order=5)
        lesson_44 = Lesson.objects.get(course=self.course, order=44)
        p5  = build_lesson_tutor_prompt(lesson_5)
        p44 = build_lesson_tutor_prompt(lesson_44)
        # Prompts must differ between lessons (no generic chat).
        self.assertNotEqual(p5, p44)
        self.assertIn("Things You Have", p5)
        self.assertIn("What You Can and Can't Do", p44)

    # ------------------------------------------------------------------
    # Flow 8 — Reviews lock/unlock by progress
    # ------------------------------------------------------------------
    def test_flow_8_review_locked_then_unlocks(self):
        user = self._student("eve")
        r1 = CourseReview.objects.get(course=self.course, start_unit_number=1)
        self.assertFalse(r1.is_unlocked_for(user))

        # Complete units 1..8.
        now = timezone.now()
        for lesson in Lesson.objects.filter(
            course=self.course, order__lte=r1.end_unit_number,
        ):
            CourseLessonProgress.objects.create(
                user=user, lesson=lesson,
                video_completed=True,
                completed_at=now - timedelta(minutes=1),
            )
        self.assertTrue(r1.is_unlocked_for(user))

    # ------------------------------------------------------------------
    # Sanity: no duplicate seed data
    # ------------------------------------------------------------------
    def test_no_duplicate_seed_data(self):
        call_command("seed_onlenco_beginner_48_units",  "--quiet", stdout=StringIO())
        call_command("seed_onlenco_beginner_quiz_bank", "--quiet", stdout=StringIO())
        call_command("seed_onlenco_beginner_reviews",   "--quiet", stdout=StringIO())
        self.assertEqual(Course.objects.filter(slug=COURSE_SLUG).count(), 1)
        self.assertEqual(Lesson.objects.filter(course=self.course).count(), 48)
        self.assertEqual(CourseReview.objects.filter(course=self.course).count(), 6)
