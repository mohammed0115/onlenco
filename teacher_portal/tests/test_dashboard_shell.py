"""Prompt 16.6 — teacher shell responsiveness + mobile drawer + RTL safety."""
from .utils import TeacherPortalTestMixin


class TeacherShellResponsiveTests(TeacherPortalTestMixin):
    def test_teacher_dashboard_renders(self):
        self.client.force_login(self.teacher)
        r = self.client.get("/teacher/dashboard/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="teacher-sidebar"')

    def test_teacher_dashboard_has_mobile_drawer(self):
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/dashboard/").content.decode()
        self.assertIn('data-ds-toggle="#teacher-sidebar"', html)
        self.assertIn("data-ds-overlay", html)
        self.assertIn("dashboard-shell.js", html)
        self.assertIn('aria-controls="teacher-sidebar"', html)

    def test_teacher_dashboard_rtl_safe(self):
        # Teacher shell resolves language from the user's preference (the
        # middleware re-activates it per request), so set it explicitly.
        self.teacher.profile.preferred_language = "ar"
        self.teacher.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/dashboard/").content.decode()
        self.assertIn('dir="rtl"', html)
        self.assertIn("ds-drawer-toggle", html)

    def test_student_cannot_access_teacher_dashboard(self):
        self.client.force_login(self.student)
        r = self.client.get("/teacher/dashboard/")
        self.assertNotEqual(r.status_code, 200)
