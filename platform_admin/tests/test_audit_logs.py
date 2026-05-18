from django.test import TestCase

from platform_admin.models import PlatformAuditLog
from platform_admin.tests.utils import PlatformAdminTestMixin


class PlatformAuditLogTests(PlatformAdminTestMixin, TestCase):
    def test_audit_logs_page_works(self):
        PlatformAuditLog.objects.create(
            actor=self.platform_admin,
            action_type="test.action",
            description="Test log",
        )
        self.client.force_login(self.platform_admin)
        response = self.client.get("/admin/audit-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test.action")
