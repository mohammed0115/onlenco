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

    # --- Prompt 16.6A.1 — shell layout regression guards ---

    def test_teacher_dashboard_desktop_shell_not_drawer(self):
        # CSS must (a) force the sidebar back into the grid >=769px and
        # (b) hide the hamburger/overlay on desktop; the drawer is gated
        # behind <=768px only.
        from django.contrib.staticfiles import finders
        css = open(finders.find("teacher_portal/css/teacher.css")).read()
        self.assertIn("@media (min-width: 769px)", css)
        self.assertIn("@media (max-width: 768px)", css)
        desktop = css.split("@media (min-width: 769px)")[1].split("@media (max-width: 768px)")[0]
        self.assertIn(".ds-drawer-toggle", desktop)
        self.assertIn("display: none", desktop)

    def test_teacher_dashboard_overlay_not_first_grid_child(self):
        # The overlay must come AFTER the sidebar in the shell grid so it
        # never steals the first grid column (the regression cause).
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/dashboard/").content.decode()
        self.assertLess(html.index('id="teacher-sidebar"'), html.index("data-ds-overlay"))

    def test_teacher_css_version_bumped(self):
        # Cache-bust param must be current so the fixed CSS actually loads
        # (non-manifest whitenoise storage relies on ?v=).
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/dashboard/").content.decode()
        self.assertIn("teacher.css?v=p166a1", html)

    def test_dashboard_shell_js_does_not_force_drawer_on_desktop(self):
        from django.contrib.staticfiles import finders
        js = open(finders.find("js/dashboard-shell.js")).read()
        # Drawer only opens via an explicit toggle click — no auto-open.
        self.assertIn("data-ds-toggle", js)
        self.assertIn('classList.add("is-open")', js)
        self.assertNotIn("open();\n})", js)  # not invoked at init
