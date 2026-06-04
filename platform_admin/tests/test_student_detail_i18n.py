"""Admin student-detail + approvals render in Arabic (no hardcoded English labels)."""
from django.test import TestCase
from django.utils import translation

from platform_admin.tests.utils import PlatformAdminTestMixin


class AdminStudentI18nTests(PlatformAdminTestMixin, TestCase):
    def _html(self, path):
        self.client.force_login(self.platform_admin)
        with translation.override("ar"):
            r = self.client.get(path)
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def test_student_detail_is_arabic(self):
        html = self._html(f"/admin/students/{self.student.pk}/")
        for ar in ["نظرة عامة", "إرسال إشعار", "إضافة ملاحظة", "إسناد كورس", "تمديد الاشتراك", "تقدّم التعلّم"]:
            self.assertIn(ar, html)
        # The previously-hardcoded English headings must be gone in Arabic mode.
        for en in [">Send notification<", ">Assign course<", ">Learning Progress<"]:
            self.assertNotIn(en, html)

    def test_student_detail_english_mode_still_english(self):
        # Language is driven by the user's profile preference (middleware),
        # not translation.override — set it to English explicitly.
        self.platform_admin.profile.preferred_language = "en"
        self.platform_admin.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.platform_admin)
        html = self.client.get(f"/admin/students/{self.student.pk}/").content.decode()
        self.assertIn("Overview", html)
        self.assertIn("Send notification", html)

    def test_approvals_is_arabic(self):
        html = self._html("/admin/student-approvals/")
        self.assertIn("موافقات الطلاب", html)
        self.assertIn("اعتماد", html)

    def test_content_review_is_arabic(self):
        html = self._html("/admin/courses/review/")
        self.assertIn("مراجعة المحتوى", html)
        self.assertIn("موافقة", html)
        self.assertNotIn(">Content Review<", html)

    def test_approvals_link_in_admin_nav(self):
        html = self._html("/admin/students/")
        self.assertIn("موافقات الطلاب", html)
        self.assertIn("/admin/student-approvals/", html)

    def test_admin_sidebar_uses_logo_image_not_icon(self):
        html = self._html("/admin/students/")
        self.assertIn("img/onlenco-logo.png", html)

    def test_approve_button_shown_for_pending_student(self):
        from accounts.models import APPROVAL_PENDING_ADMIN
        p = self.student.profile
        p.approval_status = APPROVAL_PENDING_ADMIN
        p.save(update_fields=["approval_status"])
        html = self._html(f"/admin/students/{self.student.pk}/")
        self.assertIn("الموافقة على الطالب", html)
        self.assertIn("student-approvals/%d/approve/" % self.student.pk, html)

    def test_approve_button_hidden_for_approved_student(self):
        from accounts.models import APPROVAL_APPROVED
        p = self.student.profile
        p.approval_status = APPROVAL_APPROVED
        p.save(update_fields=["approval_status"])
        html = self._html(f"/admin/students/{self.student.pk}/")
        self.assertNotIn("الموافقة على الطالب", html)
