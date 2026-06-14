"""Placement-based access: a student opens every level up to their CEFR level."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from courses.models import Course, CourseEnrollment, CourseLevel
from courses.services.student_flow import (
    can_access_course, levels_up_to, visible_level_codes_for_user,
)


User = get_user_model()

LEVEL_ORDER = {"A0": 0, "A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}


def _course(code, *, is_free=False):
    level = CourseLevel.objects.get_or_create(
        code=code, defaults={"name": f"L{code}", "order": LEVEL_ORDER[code]})[0]
    return Course.objects.create(
        title=f"C{code}", slug=f"c-{code.lower()}", level=level,
        status="published", is_active=True, is_free=is_free)


class LevelsUpToTests(TestCase):
    def test_cumulative_levels(self):
        self.assertEqual(levels_up_to("B1"), ("A0", "A1", "A2", "B1"))
        self.assertEqual(levels_up_to("A0"), ("A0",))

    def test_unknown_level(self):
        self.assertEqual(levels_up_to("ZZ"), ())


class PlacementAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="b1", password="pw")
        self.user.profile.cefr_level = "B1"
        self.user.profile.subscription_status = "active"
        self.user.profile.save()

    def test_subscribed_b1_opens_levels_up_to_b1(self):
        for code in ("A0", "A1", "A2", "B1"):
            self.assertTrue(can_access_course(self.user, _course(code)),
                            f"{code} should be open for a B1 student")

    def test_subscribed_b1_cannot_open_higher_levels(self):
        for code in ("B2", "C1", "C2"):
            self.assertFalse(can_access_course(self.user, _course(code)),
                             f"{code} should be locked for a B1 student")

    def test_free_course_always_open_even_above_level(self):
        self.assertTrue(can_access_course(self.user, _course("C2", is_free=True)))

    def test_unsubscribed_blocked_on_paid_within_level(self):
        self.user.profile.subscription_status = "none"
        self.user.profile.save(update_fields=["subscription_status"])
        self.assertFalse(can_access_course(self.user, _course("A1")))

    def test_subscribed_without_placement_not_restricted(self):
        u = User.objects.create_user(username="np", password="pw")
        u.profile.cefr_level = ""
        u.profile.subscription_status = "active"
        u.profile.save()
        self.assertTrue(can_access_course(u, _course("C1")))

    def test_visible_levels_are_cumulative(self):
        self.assertEqual(visible_level_codes_for_user(self.user),
                         ("A0", "A1", "A2", "B1"))


class AdminAssignedCourseAccessTests(TestCase):
    """An admin-assigned (enrolled) course is accessible + visible even when it
    sits above the student's placement level."""

    def setUp(self):
        self.user = User.objects.create_user(username="a0", password="pw")
        self.user.profile.cefr_level = "A0"
        self.user.profile.subscription_status = "active"
        self.user.profile.save()

    def test_enrolled_higher_level_course_is_accessible(self):
        b1 = _course("B1")
        # Without enrollment, an A0 student can't open a B1 course.
        self.assertFalse(can_access_course(self.user, b1))
        # Admin assigns it → enrollment → now accessible.
        CourseEnrollment.objects.create(user=self.user, course=b1, status="active")
        self.assertTrue(can_access_course(self.user, b1))

    def test_enrolled_levels_are_visible(self):
        a1 = _course("A1")
        b1 = _course("B1")
        CourseEnrollment.objects.create(user=self.user, course=a1, status="active")
        CourseEnrollment.objects.create(user=self.user, course=b1, status="active")
        visible = visible_level_codes_for_user(self.user)
        self.assertIn("A0", visible)   # own level
        self.assertIn("A1", visible)   # assigned
        self.assertIn("B1", visible)   # assigned

    def test_enrollment_still_needs_subscription(self):
        self.user.profile.subscription_status = "none"
        self.user.profile.save(update_fields=["subscription_status"])
        b1 = _course("B1")
        CourseEnrollment.objects.create(user=self.user, course=b1, status="active")
        self.assertFalse(can_access_course(self.user, b1))
