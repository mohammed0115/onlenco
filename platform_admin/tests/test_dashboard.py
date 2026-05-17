from django.test import TestCase
from django.utils import translation

from platform_admin.tests.utils import PlatformAdminTestMixin


class PlatformDashboardTests(PlatformAdminTestMixin, TestCase):
    def test_dashboard_metrics_load(self):
        self.platform_admin.profile.preferred_language = "en"
        self.platform_admin.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.platform_admin)
        response = self.client.get("/control/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total Students")
        self.assertContains(response, "Pending Payments")

    def test_arabic_rtl_renders(self):
        self.client.force_login(self.platform_admin)
        with translation.override("ar"):
            response = self.client.get("/control/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="rtl"')
        self.assertContains(response, "لوحة إدارة Onlenco")

    def test_english_ltr_renders(self):
        self.platform_admin.profile.preferred_language = "en"
        self.platform_admin.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.platform_admin)
        with translation.override("en"):
            response = self.client.get("/control/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dir="ltr"')
        self.assertContains(response, "Onlenco Control Center")
