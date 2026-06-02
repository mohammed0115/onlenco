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

    # --- Prompt 16.6A.2 — shell layout rebuild guards ---

    def _control_css(self):
        from django.contrib.staticfiles import finders
        return open(finders.find("platform_admin/css/control.css")).read()

    def test_admin_shell_desktop_sidebar_not_drawer(self):
        css = self._control_css()
        self.assertIn("@media (min-width: 1024px)", css)
        self.assertIn("@media (max-width: 1023px)", css)
        desktop = css.split("@media (min-width: 1024px)")[1].split("@media (max-width: 1023px)")[0]
        self.assertIn("position: sticky", desktop)
        self.assertNotIn("position: fixed", desktop)

    def test_admin_hamburger_hidden_on_desktop(self):
        css = self._control_css()
        desktop = css.split("@media (min-width: 1024px)")[1].split("@media (max-width: 1023px)")[0]
        self.assertIn(".ds-drawer-toggle { display: none !important; }", desktop)
        self.assertIn(".ds-overlay { display: none !important; }", desktop)
        self.assertIn("grid-template-columns: 16rem minmax(0, 1fr)", desktop)

    def test_admin_css_version_bumped(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get("/admin/").content.decode()
        self.assertIn("control.css?v=p166a2", html)
