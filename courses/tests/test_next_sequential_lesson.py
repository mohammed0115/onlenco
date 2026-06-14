"""next_sequential_lesson_for_user: day 1 → lesson 1, day 2 → lesson 2 …"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from courses.models import Course, CourseLevel, CourseLessonProgress, Lesson
from courses.services.student_flow import next_sequential_lesson_for_user


User = get_user_model()


class NextSequentialLessonTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="seq", password="pw")
        self.user.profile.cefr_level = "A1"
        self.user.profile.save(update_fields=["cefr_level"])
        level = CourseLevel.objects.get_or_create(
            code="A1", defaults={"name": "Elementary", "order": 1})[0]
        self.course = Course.objects.create(
            title="C", slug="seq-c", level=level, status="published",
            is_active=True, is_free=True)
        self.lessons = [
            Lesson.objects.create(
                course=self.course, title=f"L{n}", content_html="<p>x</p>",
                status="published", is_active=True, order=n, code=f"SEQL{n}")
            for n in (1, 2, 3)
        ]

    def _complete(self, lesson):
        CourseLessonProgress.objects.create(
            user=self.user, lesson=lesson,
            video_completed=True, quiz_passed=True, completed_at=timezone.now())

    def test_first_day_returns_first_lesson(self):
        self.assertEqual(next_sequential_lesson_for_user(self.user), self.lessons[0])

    def test_after_completing_first_returns_second(self):
        self._complete(self.lessons[0])
        self.assertEqual(next_sequential_lesson_for_user(self.user), self.lessons[1])

    def test_skips_all_completed_to_next_uncompleted(self):
        self._complete(self.lessons[0])
        self._complete(self.lessons[1])
        self.assertEqual(next_sequential_lesson_for_user(self.user), self.lessons[2])

    def test_all_complete_returns_last_for_replay(self):
        for l in self.lessons:
            self._complete(l)
        self.assertEqual(next_sequential_lesson_for_user(self.user), self.lessons[2])

    def test_started_but_not_completed_still_counts_as_next(self):
        # A progress row without completed_at must NOT skip the lesson.
        CourseLessonProgress.objects.create(
            user=self.user, lesson=self.lessons[0], video_completed=True)
        self.assertEqual(next_sequential_lesson_for_user(self.user), self.lessons[0])
