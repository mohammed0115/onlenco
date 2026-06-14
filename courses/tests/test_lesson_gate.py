"""Tests for the sequential daily-drip lesson gate (non-A0 courses)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseLessonProgress, CourseLevel, Lesson
from courses.services.lesson_gate import annotate_lesson_states, can_open_lesson

User = get_user_model()


class LessonGateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="driptest", password="pw")
        self.level = CourseLevel.objects.create(
            code="B1", name="B1", order=4, is_active=True,
        )
        self.course = Course.objects.create(
            title="Drip Course", slug="drip-course", level=self.level,
            status="published", is_active=True, is_free=True,
        )
        self.lessons = [
            Lesson.objects.create(
                course=self.course, title=f"Lesson {i}", order=i,
                status="published", is_active=True,
            )
            for i in range(1, 4)
        ]

    def _complete(self, lesson, *, days_ago=0):
        return CourseLessonProgress.objects.create(
            user=self.user, lesson=lesson, video_completed=True,
            completed_at=timezone.now() - timedelta(days=days_ago),
        )

    def _states(self, has_access=True):
        rows = annotate_lesson_states(
            course=self.course, lessons=self.lessons,
            user=self.user, has_access=has_access,
        )
        return [r["state"] for r in rows]

    # --- service: drip rule ------------------------------------------------

    def test_fresh_student_only_first_lesson_open(self):
        self.assertEqual(self._states(), ["unlocked", "locked", "locked"])

    def test_completion_yesterday_unlocks_next(self):
        self._complete(self.lessons[0], days_ago=1)
        self.assertEqual(self._states(), ["completed", "unlocked", "locked"])

    def test_completing_a_lesson_unlocks_the_next_immediately(self):
        # No calendar-day wait: finishing lesson 1 opens lesson 2 right away.
        self._complete(self.lessons[0], days_ago=0)
        self.assertEqual(self._states(), ["completed", "unlocked", "locked"])

    def test_two_days_of_progress_open_third_lesson(self):
        self._complete(self.lessons[0], days_ago=2)
        self._complete(self.lessons[1], days_ago=1)
        self.assertEqual(self._states(), ["completed", "completed", "unlocked"])

    def test_drip_disabled_opens_every_lesson(self):
        self.course.drip_enabled = False
        self.course.save(update_fields=["drip_enabled"])
        self.assertEqual(self._states(), ["unlocked", "unlocked", "unlocked"])

    def test_no_access_locks_everything(self):
        rows = annotate_lesson_states(
            course=self.course, lessons=self.lessons,
            user=self.user, has_access=False,
        )
        self.assertTrue(all(not r["can_open"] for r in rows))

    def test_locked_lesson_has_no_available_date(self):
        # With unlock-on-completion there is no scheduled "available on" date —
        # a lesson is simply locked until its predecessor is finished.
        rows = annotate_lesson_states(
            course=self.course, lessons=self.lessons,
            user=self.user, has_access=True,
        )
        self.assertEqual(rows[1]["state"], "locked")
        self.assertIsNone(rows[1]["available_on"])

    def test_can_open_lesson_guard(self):
        self.assertTrue(can_open_lesson(
            course=self.course, lesson=self.lessons[0],
            user=self.user, has_access=True,
        ))
        self.assertFalse(can_open_lesson(
            course=self.course, lesson=self.lessons[1],
            user=self.user, has_access=True,
        ))

    # --- view guard --------------------------------------------------------

    def test_locked_lesson_url_redirects_to_course(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("courses:lesson_detail", args=[self.course.pk, self.lessons[1].pk])
        )
        self.assertRedirects(
            resp, reverse("courses:course_detail", args=[self.course.pk])
        )

    def test_unlocked_lesson_url_opens(self):
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("courses:lesson_detail", args=[self.course.pk, self.lessons[0].pk])
        )
        self.assertEqual(resp.status_code, 200)

    def test_lesson_opens_after_previous_completed_a_day_ago(self):
        self._complete(self.lessons[0], days_ago=1)
        self.client.force_login(self.user)
        resp = self.client.get(
            reverse("courses:lesson_detail", args=[self.course.pk, self.lessons[1].pk])
        )
        self.assertEqual(resp.status_code, 200)
