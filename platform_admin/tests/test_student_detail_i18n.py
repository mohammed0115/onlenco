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
