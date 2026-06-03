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
        self.assertIn("control.css?v=p166c-design-20260603", html)

    def test_admin_lesson_create_page_renders_content(self):
        self.client.force_login(self.platform_admin)
        response = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="control-shell"')
        self.assertContains(response, 'class="control-content"')

    def test_admin_lesson_create_page_contains_form(self):
        self.client.force_login(self.platform_admin)
        response = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form", html=False)
        self.assertContains(response, "lesson-content-editor")

    def test_admin_lesson_create_page_uses_control_shell(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/").content.decode()
        self.assertIn("control.css?v=p166c-design-20260603", html)
        self.assertIn('id="control-sidebar"', html)
        self.assertIn('class="control-main"', html)

    def test_admin_lesson_create_page_not_blank(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/").content.decode()
        self.assertIn("درس جديد", html)
        self.assertIn("حفظ الدرس", html)

    def test_admin_lesson_create_page_no_duplicate_sidebar(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/").content.decode()
        self.assertEqual(html.count('id="control-sidebar"'), 1)

    def test_admin_lesson_create_page_loads_css_version(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/").content.decode()
        self.assertIn("control.css?v=p166c-design-20260603", html)

    def test_admin_sidebar_visible_and_main_visible(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/").content.decode()
        self.assertIn('class="control-sidebar', html)
        self.assertIn('class="control-main"', html)

    def test_placement_question_new_not_blank(self):
        self.client.force_login(self.platform_admin)
        response = self.client.get("/admin/placement-questions/new/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form", html=False)
        self.assertContains(response, "pq-builder")

    def test_rtl_shell_does_not_hide_content(self):
        self.client.force_login(self.platform_admin)
        with translation.override("ar"):
            html = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/").content.decode()
        self.assertIn('dir="rtl"', html)
        self.assertIn("control-content", html)

    def test_admin_students_page_has_table_wrap(self):
        self.client.force_login(self.platform_admin)
        response = self.client.get("/admin/students/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="table-wrap"')

    def test_admin_students_page_uses_single_shell(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get("/admin/students/").content.decode()
        self.assertEqual(html.count('class="control-shell"'), 1)

    def test_admin_students_page_has_main_content(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get("/admin/students/").content.decode()
        self.assertIn('class="control-main"', html)
        self.assertIn('class="control-content"', html)

    def test_admin_students_page_no_duplicate_sidebar(self):
        self.client.force_login(self.platform_admin)
        html = self.client.get("/admin/students/").content.decode()
        self.assertEqual(html.count('id="control-sidebar"'), 1)

    def test_table_wrap_used_on_admin_tables(self):
        self.client.force_login(self.platform_admin)
        students_html = self.client.get("/admin/students/").content.decode()
        courses_html = self.client.get("/admin/courses/").content.decode()
        self.assertIn('class="table-wrap"', students_html)
        self.assertIn('class="table-wrap"', courses_html)

    def test_all_admin_table_pages_use_table_wrap(self):
        self.client.force_login(self.platform_admin)
        students_html = self.client.get("/admin/students/").content.decode()
        teachers_html = self.client.get("/admin/teachers/").content.decode()
        courses_html = self.client.get("/admin/courses/").content.decode()
        plans_html = self.client.get("/admin/plans/").content.decode()
        self.assertIn('class="table-wrap"', students_html)
        self.assertIn('class="table-wrap"', teachers_html)
        self.assertIn('class="table-wrap"', courses_html)
        self.assertIn('class="table-wrap"', plans_html)

    def test_shell_main_has_min_width_zero_class_or_css(self):
        css = self._control_css()
        self.assertIn(".control-main", css)
        self.assertIn("min-width: 0", css)

    def test_shell_css_contains_minmax_zero_main(self):
        css = self._control_css()
        self.assertIn("grid-template-columns: 16rem minmax(0, 1fr)", css)

    def test_shell_css_does_not_use_100vw_for_main(self):
        css = self._control_css()
        self.assertNotIn("100vw", css)

    def test_mobile_drawer_does_not_create_page_overflow_guard(self):
        css = self._control_css()
        self.assertIn("overflow-x: hidden", css)
        self.assertIn("overflow-x: clip", css)
