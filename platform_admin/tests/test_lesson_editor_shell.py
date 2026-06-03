"""Prompt 16.6B.0 — admin lesson editor shell renders fully (not blank)."""
from django.test import TestCase
from django.utils import translation

from platform_admin.tests.utils import PlatformAdminTestMixin


class AdminLessonEditorShellTests(PlatformAdminTestMixin, TestCase):
    def _html(self, status=200):
        self.client.force_login(self.platform_admin)
        r = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/")
        self.assertEqual(r.status_code, status)
        return r.content.decode()

    def test_admin_lesson_create_page_renders_content(self):
        html = self._html()
        self.assertIn("<form", html)
        self.assertIn("control-content", html)   # main content block rendered

    def test_admin_lesson_create_page_contains_form(self):
        html = self._html()
        self.assertIn("<form", html)
        self.assertIn("</form>", html)

    def test_admin_lesson_create_page_uses_control_shell(self):
        html = self._html()
        self.assertIn('id="control-sidebar"', html)
        self.assertIn("control.css", html)

    def test_admin_lesson_create_page_not_blank(self):
        html = self._html()
        # A blank page would be tiny; a real shell + form is substantial.
        self.assertGreater(len(html), 4000)

    def test_admin_lesson_create_page_no_duplicate_sidebar(self):
        html = self._html()
        self.assertEqual(html.count('id="control-sidebar"'), 1)

    def test_admin_lesson_create_page_loads_css_version(self):
        html = self._html()
        self.assertIn("control.css?v=", html)

    def test_admin_sidebar_visible_and_main_visible(self):
        html = self._html()
        self.assertIn("control-sidebar", html)
        self.assertIn("control-main", html)

    def test_rtl_shell_does_not_hide_content(self):
        self.client.force_login(self.platform_admin)
        with translation.override("ar"):
            r = self.client.get(f"/admin/courses/{self.course.pk}/lessons/new/")
        html = r.content.decode()
        self.assertEqual(r.status_code, 200)
        self.assertIn('dir="rtl"', html)
        self.assertIn("<form", html)
