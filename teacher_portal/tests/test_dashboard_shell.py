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

    # --- Prompt 16.6A.2 — shell layout rebuild guards ---

    def _teacher_css(self):
        from django.contrib.staticfiles import finders
        return open(finders.find("teacher_portal/css/teacher.css")).read()

    def test_teacher_shell_desktop_sidebar_not_drawer(self):
        # Desktop (>=1024px) must keep the sidebar in-grid (sticky, not fixed)
        # and the drawer must be gated behind <=1023px only.
        css = self._teacher_css()
        self.assertIn("@media (min-width: 1024px)", css)
        self.assertIn("@media (max-width: 1023px)", css)
        desktop = css.split("@media (min-width: 1024px)")[1].split("@media (max-width: 1023px)")[0]
        self.assertIn("position: sticky", desktop)
        self.assertNotIn("position: fixed", desktop)

    def test_hamburger_hidden_on_desktop(self):
        # The desktop block must hide the hamburger + overlay decisively.
        css = self._teacher_css()
        desktop = css.split("@media (min-width: 1024px)")[1].split("@media (max-width: 1023px)")[0]
        self.assertIn(".ds-drawer-toggle { display: none !important; }", desktop)
        self.assertIn(".ds-overlay { display: none !important; }", desktop)

    def test_sidebar_does_not_overlap_content_desktop(self):
        # Two-column grid keeps content beside (not under) the sidebar.
        css = self._teacher_css()
        desktop = css.split("@media (min-width: 1024px)")[1].split("@media (max-width: 1023px)")[0]
        self.assertIn("grid-template-columns: 16rem minmax(0, 1fr)", desktop)

    def test_teacher_dashboard_overlay_not_first_grid_child(self):
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/dashboard/").content.decode()
        self.assertLess(html.index('id="teacher-sidebar"'), html.index("data-ds-overlay"))

    def test_teacher_css_version_bumped(self):
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/dashboard/").content.decode()
        self.assertIn("teacher.css?v=p166a3", html)

    def test_dashboard_shell_js_exits_early_on_desktop(self):
        from django.contrib.staticfiles import finders
        js = open(finders.find("js/dashboard-shell.js")).read()
        self.assertIn("data-ds-toggle", js)
        self.assertIn('classList.add("is-open")', js)
        # open() bails out when the toggle is hidden (desktop guard).
        self.assertIn('getComputedStyle(btn).display === "none"', js)
