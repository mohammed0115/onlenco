from django.test import TestCase

from platform_admin.tests.utils import PlatformAdminTestMixin


class PlatformAIMonitoringTests(PlatformAdminTestMixin, TestCase):
    def test_ai_dashboard_permission_works(self):
        self.client.force_login(self.ai_admin)
        response = self.client.get("/control/ai/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AI requests today")
