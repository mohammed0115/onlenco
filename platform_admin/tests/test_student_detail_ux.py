"""Prompt 16.6D — admin student-detail UX: compact action panel, tab chips,
content grid, wrapped tables, bilingual labels, bumped CSS version."""
from django.test import TestCase
from django.utils import translation

from platform_admin.tests.utils import PlatformAdminTestMixin


class StudentDetailUxTests(PlatformAdminTestMixin, TestCase):
    def _html(self, path="auto"):
        self.client.force_login(self.platform_admin)
        if path == "auto":
            path = f"/admin/students/{self.student.pk}/"
        with translation.override("ar"):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def _control_css(self):
        from django.contrib.staticfiles import finders
        return open(finders.find("platform_admin/css/control.css")).read()

    def test_admin_student_detail_renders_clean_shell(self):
        html = self._html()
        self.assertEqual(html.count('id="control-sidebar"'), 1)
        self.assertIn("control-shell", html)
        self.assertIn('class="control-main"', html)

    def test_admin_student_detail_uses_compact_action_panel(self):
        html = self._html()
        self.assertIn("student-actions", html)
        self.assertIn("ta-aside", html)
        self.assertIn("ta-btn", html)
        self.assertGreaterEqual(html.count("ta-mini"), 5)

    def test_admin_student_detail_tabs_are_localized_arabic(self):
        html = self._html()
        self.assertIn("tab-chip", html)
        self.assertIn("tabs-wrap", html)
        for ar in ["نظرة عامة", "تقدّم التعلّم", "المدفوعات", "الملاحظات"]:
            self.assertIn(ar, html)

    def test_admin_student_detail_learning_progress_wrapped(self):
        from courses.models import Course, CourseEnrollment, CourseLevel
        level = CourseLevel.objects.create(code="UXA1", name="UX A1", order=99)
        course = Course.objects.create(title="UX Course", slug="ux-course", level=level, status="published")
        CourseEnrollment.objects.create(user=self.student, course=course, progress_percentage=42)
        html = self._html()
        self.assertIn("table-wrap", html)
        self.assertIn("progress-mini", html)  # progress bar renders for the enrollment

    def test_admin_students_list_table_wrapped(self):
        html = self._html("/admin/students/")
        self.assertIn('class="table-wrap"', html)

    def test_no_raw_english_action_labels_in_arabic_student_detail(self):
        html = self._html()
        for en in ["Send notification", "Extend subscription", "Deactivate account", "Assign course", "Reset placement"]:
            self.assertNotIn(en, html)

    def test_css_version_bumped_to_p166d(self):
        html = self._html()
        self.assertIn("p166d-student-detail-ux-20260604", html)

    def test_action_buttons_not_grid_stretched(self):
        css = self._control_css()
        self.assertIn(".student-actions .ta-btn", css)
        self.assertIn("max-height: 52px", css)
        # The legacy grid-stretch must not resurrect.
        self.assertNotIn(".action-box { display: grid; place-items: stretch; }", css)

    def test_content_grid_present(self):
        html = self._html()
        self.assertIn("content-grid", html)
        self.assertIn("card-wide", html)

    def test_student_detail_mobile_drawer_guard_classes_present(self):
        html = self._html()
        self.assertIn("ds-drawer", html)
        css = self._control_css()
        self.assertIn("overflow-x: clip", css)
        self.assertIn("min-width: 0", css)


from teacher_portal.tests.utils import TeacherPortalTestMixin  # noqa: E402


class TeacherStudentsListUxTests(TeacherPortalTestMixin):
    def test_teacher_students_list_table_wrapped(self):
        self.client.force_login(self.teacher)
        html = self.client.get("/teacher/students/").content.decode()
        self.assertIn('class="table-wrap"', html)
