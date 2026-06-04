"""Prompt 3 — student groups + dashboard next-live-session enhancement."""
from datetime import timedelta

from django.utils import timezone

from teacher_portal.models import LiveSession
from teacher_portal.services import dashboard_service, student_service
from teacher_portal.tests.utils import TeacherPortalTestMixin


class StudentGroupsTests(TeacherPortalTestMixin):
    def setUp(self):
        super().setUp()
        # student is enrolled in self.course (teacher's); give them a level.
        self.student.profile.cefr_level = "A2"
        self.student.profile.save(update_fields=["cefr_level"])

    def test_groups_service_groups_by_level(self):
        groups = student_service.teacher_student_groups(self.teacher)
        levels = {g["level"] for g in groups}
        self.assertIn("A2", levels)
        a2 = next(g for g in groups if g["level"] == "A2")
        self.assertEqual(a2["count"], 1)
        self.assertEqual(a2["students"][0]["student"].pk, self.student.pk)

    def test_groups_excludes_other_teachers_students(self):
        # student2 is enrolled in other_course (teacher2's) — must not appear.
        groups = student_service.teacher_student_groups(self.teacher)
        all_ids = {r["student"].pk for g in groups for r in g["students"]}
        self.assertNotIn(self.student2.pk, all_ids)

    def test_groups_page_renders(self):
        self.client.force_login(self.teacher)
        r = self.client.get("/teacher/groups/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "A2")

    def test_groups_page_requires_teacher(self):
        self.client.force_login(self.student)
        r = self.client.get("/teacher/groups/")
        self.assertNotEqual(r.status_code, 200)


class DashboardNextSessionTests(TeacherPortalTestMixin):
    def test_next_live_session_in_context(self):
        s = LiveSession.objects.create(
            teacher=self.teacher, course=self.course, title="Upcoming",
            scheduled_at=timezone.now() + timedelta(days=1),
        )
        ctx = dashboard_service.dashboard_context(self.teacher)
        self.assertEqual(ctx["next_live_session"].pk, s.pk)

    def test_no_next_session_is_none(self):
        ctx = dashboard_service.dashboard_context(self.teacher)
        self.assertIsNone(ctx["next_live_session"])

    def test_cancelled_session_not_shown(self):
        LiveSession.objects.create(
            teacher=self.teacher, course=self.course, title="X",
            scheduled_at=timezone.now() + timedelta(days=1), status="cancelled",
        )
        ctx = dashboard_service.dashboard_context(self.teacher)
        self.assertIsNone(ctx["next_live_session"])
