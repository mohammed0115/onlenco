"""Role + object-level permission rules.

These guard the spec's most important invariant: a Teacher can only
see / edit their own courses and lessons; an Academic Admin sees all;
Support sees view-only; Finance sees only payments.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from courses import permissions as perms
from courses.models import Course, CourseLevel, Lesson

User = get_user_model()


class _Setup(TestCase):
    """Shared fixtures: 1 academic admin, 2 teachers, 1 support, 1 finance,
    plus 2 courses (one per teacher) and a lesson on each."""

    def setUp(self):
        # Seed the role groups (idempotent).
        from django.core.management import call_command
        call_command("seed_role_groups", verbosity=0)

        def _grp(name): return Group.objects.get(name=name)

        self.acad   = User.objects.create_user("acad",   password="pw", is_staff=True)
        self.t1     = User.objects.create_user("t1",     password="pw", is_staff=True)
        self.t2     = User.objects.create_user("t2",     password="pw", is_staff=True)
        self.support = User.objects.create_user("support", password="pw", is_staff=True)
        self.finance = User.objects.create_user("finance", password="pw", is_staff=True)
        self.outsider = User.objects.create_user("outsider", password="pw")

        self.acad.groups.add(_grp(perms.GROUP_ACADEMIC_ADMIN))
        self.t1.groups.add(_grp(perms.GROUP_TEACHER))
        self.t2.groups.add(_grp(perms.GROUP_TEACHER))
        self.support.groups.add(_grp(perms.GROUP_SUPPORT_ADMIN))
        self.finance.groups.add(_grp(perms.GROUP_FINANCE_ADMIN))

        self.level = CourseLevel.objects.create(code="A1", name="A1", order=1)
        self.c_t1 = Course.objects.create(
            title="T1 course", slug="t1", level=self.level,
            teacher=self.t1, created_by=self.t1,
        )
        self.c_t2 = Course.objects.create(
            title="T2 course", slug="t2", level=self.level,
            teacher=self.t2, created_by=self.t2,
        )
        self.l_t1 = Lesson.objects.create(course=self.c_t1, title="L1", created_by=self.t1)
        self.l_t2 = Lesson.objects.create(course=self.c_t2, title="L2", created_by=self.t2)


class RoleHelperTests(_Setup):
    def test_role_helpers(self):
        self.assertTrue(perms.is_academic_admin(self.acad))
        self.assertTrue(perms.is_teacher(self.t1))
        self.assertTrue(perms.is_support_admin(self.support))
        self.assertTrue(perms.is_finance_admin(self.finance))

        # Cross-role: a teacher is not an academic admin.
        self.assertFalse(perms.is_academic_admin(self.t1))
        self.assertFalse(perms.is_finance_admin(self.support))

    def test_anonymous_user_has_no_role(self):
        from django.contrib.auth.models import AnonymousUser
        anon = AnonymousUser()
        self.assertFalse(perms.is_academic_admin(anon))
        self.assertFalse(perms.is_teacher(anon))


class CanEditCourseTests(_Setup):
    def test_academic_admin_can_edit_anything(self):
        self.assertTrue(perms.can_edit_course(self.acad, self.c_t1))
        self.assertTrue(perms.can_edit_course(self.acad, self.c_t2))

    def test_teacher_can_only_edit_own_courses(self):
        self.assertTrue(perms.can_edit_course(self.t1, self.c_t1))
        self.assertFalse(perms.can_edit_course(self.t1, self.c_t2))

    def test_support_cannot_edit_courses(self):
        self.assertFalse(perms.can_edit_course(self.support, self.c_t1))
        self.assertFalse(perms.can_edit_course(self.finance, self.c_t1))

    def test_only_academic_can_publish(self):
        self.assertTrue(perms.can_publish_course(self.acad, self.c_t1))
        self.assertFalse(perms.can_publish_course(self.t1, self.c_t1))


class FilterCoursesTests(_Setup):
    def test_filter_for_academic_admin_returns_all(self):
        qs = perms.filter_courses_for(self.acad, Course.objects.all())
        self.assertEqual(qs.count(), 2)

    def test_filter_for_teacher_returns_only_own(self):
        qs = perms.filter_courses_for(self.t1, Course.objects.all())
        self.assertEqual(list(qs.values_list("slug", flat=True)), ["t1"])

    def test_filter_for_support_returns_none(self):
        qs = perms.filter_courses_for(self.support, Course.objects.all())
        self.assertEqual(qs.count(), 0)


class FilterLessonsTests(_Setup):
    def test_teacher_sees_only_own_lessons(self):
        qs = perms.filter_lessons_for(self.t1, Lesson.objects.all())
        self.assertEqual(list(qs.values_list("title", flat=True)), ["L1"])

    def test_academic_admin_sees_all_lessons(self):
        qs = perms.filter_lessons_for(self.acad, Lesson.objects.all())
        self.assertEqual(qs.count(), 2)


class SeedRoleGroupsTests(TestCase):
    def test_all_five_groups_seeded(self):
        from django.core.management import call_command
        call_command("seed_role_groups", verbosity=0)
        names = set(Group.objects.values_list("name", flat=True))
        for expected in perms.ALL_GROUPS:
            self.assertIn(expected, names)

    def test_idempotent(self):
        from django.core.management import call_command
        call_command("seed_role_groups", verbosity=0)
        call_command("seed_role_groups", verbosity=0)
        # Run twice — should not raise or duplicate.
        for name in perms.ALL_GROUPS:
            self.assertEqual(Group.objects.filter(name=name).count(), 1)
