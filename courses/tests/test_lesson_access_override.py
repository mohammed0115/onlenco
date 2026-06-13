"""Per-lesson access override (admin lock/unlock a single lesson).

Covers:
  * can_access_lesson() — inherit / free / locked semantics.
  * Student HTTP gate honours the override on the lesson step view.
  * Admin "set access" endpoint flips the field + writes an audit event.
  * set_course_access management command (course + lesson modes).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from courses.models import Course, CourseLevel, Lesson, LessonReviewEvent
from courses.services.student_flow import can_access_lesson


User = get_user_model()


def _level(code="A0", order=0):
    return CourseLevel.objects.get_or_create(
        code=code, defaults={"name": f"Level {code}", "order": order})[0]


def _lesson(*, course, order=1, access=Lesson.ACCESS_INHERIT):
    return Lesson.objects.create(
        course=course, title=f"L{order}", content_html="<p>x</p>",
        status="published", is_active=True, order=order, access_override=access,
    )


class CanAccessLessonTests(TestCase):
    def setUp(self):
        self.sub = User.objects.create_user(username="sub", password="pw")
        self.sub.profile.subscription_status = "active"
        self.sub.profile.save(update_fields=["subscription_status"])
        self.free_user = User.objects.create_user(username="free", password="pw")

        self.free_course = Course.objects.create(
            title="Free", slug="free-c", level=_level(), status="published",
            is_active=True, is_free=True)
        self.paid_course = Course.objects.create(
            title="Paid", slug="paid-c", level=_level("A1", 1),
            status="published", is_active=True, is_free=False)

    def test_inherit_follows_free_course(self):
        l = _lesson(course=self.free_course)
        self.assertTrue(can_access_lesson(self.free_user, l))

    def test_inherit_follows_paid_course(self):
        l = _lesson(course=self.paid_course)
        self.assertFalse(can_access_lesson(self.free_user, l))
        self.assertTrue(can_access_lesson(self.sub, l))

    def test_locked_override_in_free_course_requires_subscription(self):
        l = _lesson(course=self.free_course, access=Lesson.ACCESS_LOCKED)
        self.assertFalse(can_access_lesson(self.free_user, l))  # locked despite free course
        self.assertTrue(can_access_lesson(self.sub, l))

    def test_free_override_in_paid_course_opens_lesson(self):
        l = _lesson(course=self.paid_course, access=Lesson.ACCESS_FREE)
        self.assertTrue(can_access_lesson(self.free_user, l))  # preview lesson


class LessonStepGateTests(TestCase):
    """The student-facing step view returns 403 for a locked lesson."""

    def setUp(self):
        self.user = User.objects.create_user(username="stu", password="pw")
        self.client.force_login(self.user)
        self.course = Course.objects.create(
            title="Free", slug="free-c", level=_level(), status="published",
            is_active=True, is_free=True)
        self.lesson = _lesson(course=self.course)

    def test_open_when_inherit_free(self):
        url = reverse("courses:lesson_detail", args=[self.course.pk, self.lesson.pk])
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_blocked_when_locked(self):
        self.lesson.access_override = Lesson.ACCESS_LOCKED
        self.lesson.save(update_fields=["access_override"])
        url = reverse("courses:lesson_detail", args=[self.course.pk, self.lesson.pk])
        self.assertEqual(self.client.get(url).status_code, 403)


class AdminSetAccessEndpointTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username="teach", password="pw")
        self.teacher.groups.add(Group.objects.get_or_create(name="Teacher")[0])
        self.client.force_login(self.teacher)
        self.course = Course.objects.create(
            title="Free", slug="free-c", level=_level(), status="published",
            is_active=True, is_free=True)
        self.lesson = _lesson(course=self.course)

    def test_lock_then_inherit_updates_field_and_audit(self):
        url = reverse("teacher_portal:content_review_set_access", args=[self.lesson.pk])

        resp = self.client.post(url, {"access": "locked"})
        self.assertEqual(resp.status_code, 302)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.access_override, "locked")
        self.assertTrue(LessonReviewEvent.objects.filter(
            lesson=self.lesson, action="set_access").exists())

        self.client.post(url, {"access": "inherit"})
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.access_override, "inherit")

    def test_invalid_access_value_is_rejected(self):
        url = reverse("teacher_portal:content_review_set_access", args=[self.lesson.pk])
        self.client.post(url, {"access": "bogus"})
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.access_override, "inherit")  # unchanged


class SetCourseAccessCommandTests(TestCase):
    def setUp(self):
        self.free_course = Course.objects.create(
            title="Beginner", slug="onlenco-beginner", level=_level(),
            status="published", is_active=True, is_free=False)
        self.lesson = _lesson(course=self.free_course)

    def test_make_course_free(self):
        call_command("set_course_access", "onlenco-beginner", "--free", verbosity=0)
        self.free_course.refresh_from_db()
        self.assertTrue(self.free_course.is_free)

    def test_all_published_free(self):
        call_command("set_course_access", "--all", "--free", verbosity=0)
        self.free_course.refresh_from_db()
        self.assertTrue(self.free_course.is_free)

    def test_lesson_lock_override(self):
        call_command("set_course_access", "--lesson", str(self.lesson.pk),
                     "--lesson-locked", verbosity=0)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.access_override, "locked")
