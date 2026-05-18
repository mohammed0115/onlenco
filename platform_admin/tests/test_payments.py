from django.test import TestCase

from platform_admin.models import PlatformAuditLog
from platform_admin.tests.utils import PlatformAdminTestMixin


class PlatformPaymentTests(PlatformAdminTestMixin, TestCase):
    def test_payment_filters_work(self):
        self.client.force_login(self.finance_admin)
        response = self.client.get("/admin/payments/", {"status": "pending"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "30000 SDG")

    def test_payment_approval_creates_audit_log(self):
        self.client.force_login(self.finance_admin)
        response = self.client.post(f"/admin/payments/{self.payment.pk}/approve/")
        self.assertEqual(response.status_code, 302)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, "approved")
        self.assertTrue(PlatformAuditLog.objects.filter(action_type="payment.approve").exists())

    def test_protected_payment_proof_not_public_to_support(self):
        self.client.force_login(self.support_admin)
        response = self.client.get(f"/admin/payments/{self.payment.pk}/proof/")
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.finance_admin)
        response = self.client.get(f"/admin/payments/{self.payment.pk}/proof/")
        self.assertEqual(response.status_code, 200)
