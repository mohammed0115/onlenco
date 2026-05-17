"""Status workflow + audit-log tests.

Cover the full draft → pending_review → published path through the
service layer (admin actions delegate to these), plus the rejected
state and audit logging via AdminActionLog.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from courses import permissions as perms
from courses.models import (
    AdminActionLog, ContentReviewLog, Course, CourseLevel, Lesson,
)
from courses.services import review_workflow
from courses.services.admin_log import log_admin_action

User = get_user_model()


class _WorkflowSetup(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command("seed_role_groups", verbosity=0)

        self.acad = User.objects.create_user("acad", password="pw", is_staff=True)
        self.acad.groups.add(Group.objects.get(name=perms.GROUP_ACADEMIC_ADMIN))
        self.teacher = User.objects.create_user("t", password="pw", is_staff=True)
        self.teacher.groups.add(Group.objects.get(name=perms.GROUP_TEACHER))

        self.level = CourseLevel.objects.create(code="A1", name="A1")
        self.course = Course.objects.create(
            title="C1", slug="c1", level=self.level,
            teacher=self.teacher, created_by=self.teacher, status="draft",
        )


class CourseWorkflowTests(_WorkflowSetup):
    def test_submit_for_review_flips_status(self):
        review_workflow.submit_for_review(
            content_object=self.course, submitted_by=self.teacher,
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, "pending_review")
        # Creates a ContentReviewLog row.
        self.assertEqual(
            ContentReviewLog.objects.filter(
                object_id=self.course.id, status="pending",
            ).count(), 1,
        )

    def test_approve_publishes_and_records_reviewer(self):
        review_workflow.submit_for_review(
            content_object=self.course, submitted_by=self.teacher,
        )
        review_workflow.approve(
            content_object=self.course, reviewed_by=self.acad, notes="LGTM",
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, "published")
        self.assertEqual(self.course.reviewed_by, self.acad)
        self.assertIsNotNone(self.course.reviewed_at)
        self.assertEqual(self.course.review_notes, "LGTM")

    def test_reject_marks_course_rejected_with_notes(self):
        review_workflow.submit_for_review(
            content_object=self.course, submitted_by=self.teacher,
        )
        review_workflow.reject(
            content_object=self.course, reviewed_by=self.acad,
            notes="Needs more examples.",
        )
        self.course.refresh_from_db()
        self.assertEqual(self.course.status, "rejected")
        self.assertEqual(self.course.review_notes, "Needs more examples.")

    def test_workflow_writes_admin_action_log(self):
        review_workflow.submit_for_review(
            content_object=self.course, submitted_by=self.teacher,
        )
        review_workflow.approve(content_object=self.course, reviewed_by=self.acad)
        action_types = set(
            AdminActionLog.objects.values_list("action_type", flat=True)
        )
        self.assertIn("course.submit_for_review", action_types)
        self.assertIn("course.approve", action_types)


class LessonWorkflowTests(_WorkflowSetup):
    def setUp(self):
        super().setUp()
        self.lesson = Lesson.objects.create(
            course=self.course, title="L1",
            created_by=self.teacher, status="draft",
        )

    def test_lesson_can_use_same_workflow(self):
        review_workflow.submit_for_review(
            content_object=self.lesson, submitted_by=self.teacher,
        )
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, "pending_review")

        review_workflow.approve(content_object=self.lesson, reviewed_by=self.acad)
        self.lesson.refresh_from_db()
        self.assertEqual(self.lesson.status, "published")
        self.assertEqual(self.lesson.reviewed_by, self.acad)


class AdminActionLogTests(TestCase):
    def test_log_admin_action_basic(self):
        admin = User.objects.create_user("a", password="pw")
        target = User.objects.create_user("b", password="pw")
        log = log_admin_action(
            admin_user=admin, action_type="course.publish",
            description="Published 1 course", target_user=target,
            metadata={"course_id": 42},
        )
        self.assertEqual(log.admin_user, admin)
        self.assertEqual(log.target_user, target)
        self.assertEqual(log.action_type, "course.publish")
        self.assertEqual(log.metadata, {"course_id": 42})

    def test_action_type_is_truncated_to_40_chars(self):
        admin = User.objects.create_user("a", password="pw")
        long = "x" * 100
        log = log_admin_action(admin_user=admin, action_type=long)
        self.assertLessEqual(len(log.action_type), 40)


class CourseAdminQuerysetTests(TestCase):
    """Sanity check that the admin's get_queryset really is teacher-scoped."""

    def setUp(self):
        from django.core.management import call_command
        call_command("seed_role_groups", verbosity=0)
        self.t1 = User.objects.create_user("t1", password="pw", is_staff=True)
        self.t2 = User.objects.create_user("t2", password="pw", is_staff=True)
        self.t1.groups.add(Group.objects.get(name=perms.GROUP_TEACHER))
        self.t2.groups.add(Group.objects.get(name=perms.GROUP_TEACHER))
        level = CourseLevel.objects.create(code="A1", name="A1")
        Course.objects.create(title="t1c", slug="t1c", level=level,
                              teacher=self.t1, created_by=self.t1)
        Course.objects.create(title="t2c", slug="t2c", level=level,
                              teacher=self.t2, created_by=self.t2)

    def test_teacher_admin_list_only_shows_own(self):
        from django.test import RequestFactory
        from django.contrib import admin as dj_admin
        from courses.admin import CourseAdmin
        rf = RequestFactory()
        req = rf.get("/admin/courses/course/")
        req.user = self.t1
        ca = CourseAdmin(Course, dj_admin.site)
        qs = ca.get_queryset(req)
        slugs = list(qs.values_list("slug", flat=True))
        self.assertEqual(slugs, ["t1c"])
