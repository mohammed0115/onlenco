from django.test import TestCase

from platform_admin.models import PlatformAuditLog
from platform_admin.tests.utils import PlatformAdminTestMixin


class PlatformStudentTests(PlatformAdminTestMixin, TestCase):
    def test_student_search_works(self):
        self.client.force_login(self.academic_admin)
        response = self.client.get("/control/students/", {"q": "Student One"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Student One")

    def test_reset_placement_creates_audit_log(self):
        self.student.profile.placement_completed = True
        self.student.profile.onboarding_completed = True
        self.student.profile.save()
        self.client.force_login(self.academic_admin)
        response = self.client.post(f"/control/students/{self.student.pk}/reset-placement/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlatformAuditLog.objects.filter(action_type="student.reset_placement").exists())

    def test_support_admin_can_add_note_but_not_approve_payment(self):
        self.client.force_login(self.support_admin)
        response = self.client.post(f"/control/students/{self.student.pk}/add-note/", {"note": "Needs help"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(PlatformAuditLog.objects.filter(action_type="student.add_note").exists())
        response = self.client.post(f"/control/payments/{self.payment.pk}/approve/")
        self.assertEqual(response.status_code, 403)
