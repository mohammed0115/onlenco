"""Prompt 16.6 — admin shell responsiveness + mobile drawer + RTL safety."""
from django.test import TestCase
from django.utils import translation

from platform_admin.tests.utils import PlatformAdminTestMixin


class AdminShellResponsiveTests(PlatformAdminTestMixin, TestCase):
    def test_dashboard_shell_renders_desktop(self):
        self.client.force_login(self.platform_admin)
        r = self.client.get("/admin/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="control-sidebar"')
        self.assertContains(r, "ds-drawer")

    def test_dashboard_shell_has_mobile_drawer(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get("/admin/").content.decode()
        # Hamburger toggle wired to the sidebar, overlay, and controller JS.
        self.assertIn('data-ds-toggle="#control-sidebar"', html)
        self.assertIn("data-ds-overlay", html)
        self.assertIn("dashboard-shell.js", html)
        self.assertIn('aria-controls="control-sidebar"', html)

    def test_dashboard_shell_rtl_safe(self):
        self.client.force_login(self.platform_admin)
        with translation.override("ar"):
            html = self.client.get("/admin/").content.decode()
        self.assertIn('dir="rtl"', html)
        # Drawer toggle still present in the Arabic layout.
        self.assertIn("ds-drawer-toggle", html)

    def test_student_cannot_access_admin_dashboard(self):
        self.client.force_login(self.student)
        r = self.client.get("/admin/")
        self.assertNotEqual(r.status_code, 200)
