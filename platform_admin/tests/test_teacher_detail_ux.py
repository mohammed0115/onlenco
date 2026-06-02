"""Prompt 16.6A.3 — teacher detail action-panel UX guards."""
from django.test import TestCase
from django.utils import translation

from platform_admin.tests.utils import PlatformAdminTestMixin


class TeacherDetailActionPanelTests(PlatformAdminTestMixin, TestCase):
    def _url(self):
        return f"/admin/teachers/{self.teacher.pk}/"

    def _html(self):
        self.client.force_login(self.platform_admin)
        return self.client.get(self._url()).content.decode()

    def test_teacher_detail_action_panel_renders_compact(self):
        html = self._html()
        self.assertIn("ta-aside", html)
        self.assertIn("ta-status", html)
        self.assertIn("ta-mini", html)
        self.assertIn("ta-btn", html)

    def test_teacher_detail_no_giant_action_blocks(self):
        # The old oversized full-height blocks used .action-box — gone now.
        html = self._html()
        self.assertNotIn("action-box", html)

    def test_teacher_detail_danger_zone_present(self):
        html = self._html()
        self.assertIn("ta-danger", html)
        self.assertIn("deactivate", html)

    def test_teacher_detail_remove_role_action_present_when_teacher(self):
        # self.teacher is in the Teacher group -> profile.is_teacher True.
        html = self._html()
        self.assertIn("remove-role", html)

    def test_teacher_detail_assign_course_action_present(self):
        html = self._html()
        self.assertIn("assign-course", html)

    def test_teacher_detail_destructive_action_requires_confirmation(self):
        html = self._html()
        self.assertIn("onsubmit=\"return confirm(", html)

    def test_teacher_detail_rtl_safe(self):
        self.client.force_login(self.platform_admin)
        with translation.override("ar"):
            html = self.client.get(self._url()).content.decode()
        self.assertIn('dir="rtl"', html)
        self.assertIn("ta-aside", html)

    def test_teacher_detail_shell_still_fixed(self):
        # Detail page extends the fixed shell; toggle wiring still present.
        html = self._html()
        self.assertIn('id="control-sidebar"', html)
        self.assertIn("data-ds-toggle", html)

    def test_student_cannot_access_admin_teacher_detail(self):
        self.client.force_login(self.student)
        r = self.client.get(self._url())
        self.assertNotEqual(r.status_code, 200)

    def test_teacher_detail_css_no_horizontal_overflow_guards(self):
        # CSS must clip the off-canvas drawer on mobile and let grid items
        # shrink, so the page never scrolls horizontally.
        from django.contrib.staticfiles import finders
        css = open(finders.find("platform_admin/css/control.css")).read()
        self.assertIn("overflow-x: clip", css)
        self.assertIn(".detail-grid > * { min-width: 0; }", css)
        self.assertIn(".ta-btn", css)
