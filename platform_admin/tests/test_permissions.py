from django.test import TestCase

from platform_admin import permissions as perms
from platform_admin.tests.utils import PlatformAdminTestMixin


class PlatformPermissionTests(PlatformAdminTestMixin, TestCase):
    def test_normal_student_cannot_access_control(self):
        self.client.force_login(self.student)
        response = self.client.get("/control/")
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_redirected(self):
        response = self.client.get("/control/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/", response["Location"])

    def test_super_admin_can_access_dashboard(self):
        self.client.force_login(self.super_admin)
        response = self.client.get("/control/")
        self.assertEqual(response.status_code, 200)

    def test_academic_admin_can_access_courses(self):
        self.client.force_login(self.academic_admin)
        response = self.client.get("/control/courses/")
        self.assertEqual(response.status_code, 200)

    def test_finance_admin_can_access_payments(self):
        self.client.force_login(self.finance_admin)
        response = self.client.get("/control/payments/")
        self.assertEqual(response.status_code, 200)

    def test_teacher_cannot_access_payments(self):
        self.client.force_login(self.teacher)
        response = self.client.get("/control/payments/")
        self.assertEqual(response.status_code, 403)

    def test_ai_dashboard_permission_works(self):
        self.client.force_login(self.ai_admin)
        response = self.client.get("/control/ai/")
        self.assertEqual(response.status_code, 200)
        self.client.force_login(self.finance_admin)
        response = self.client.get("/control/ai/")
        self.assertEqual(response.status_code, 403)

    def test_read_only_admin_can_view_not_mutate(self):
        self.assertTrue(perms.has_capability(self.readonly_admin, perms.CAP_COURSES_VIEW))
        self.assertFalse(perms.can_mutate(self.readonly_admin, perms.CAP_COURSES_REVIEW))
