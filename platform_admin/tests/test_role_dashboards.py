from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from platform_admin.services.role_dashboards import dashboard_url_for

from .utils import PlatformAdminTestMixin


class RoleDashboardRoutingTests(PlatformAdminTestMixin, TestCase):
    """The /control/ entry point should redirect each single-role admin to
    their tailored dashboard, while super/platform admins (and multi-role
    accounts) stay on the shared overview.
    """

    def test_dashboard_url_for_superuser_is_overview(self):
        self.assertEqual(dashboard_url_for(self.super_admin), "platform_admin:dashboard")

    def test_dashboard_url_for_platform_admin_is_overview(self):
        self.assertEqual(dashboard_url_for(self.platform_admin), "platform_admin:dashboard")

    def test_dashboard_url_for_academic_admin_is_academic(self):
        self.assertEqual(
            dashboard_url_for(self.academic_admin), "platform_admin:dashboard_academic"
        )

    def test_dashboard_url_for_finance_admin_is_finance(self):
        self.assertEqual(
            dashboard_url_for(self.finance_admin), "platform_admin:dashboard_finance"
        )

    def test_dashboard_url_for_support_admin_is_support(self):
        self.assertEqual(
            dashboard_url_for(self.support_admin), "platform_admin:dashboard_support"
        )

    def test_dashboard_url_for_ai_admin_is_ai(self):
        self.assertEqual(
            dashboard_url_for(self.ai_admin), "platform_admin:dashboard_ai"
        )

    def test_dashboard_url_for_readonly_admin_is_readonly(self):
        self.assertEqual(
            dashboard_url_for(self.readonly_admin), "platform_admin:dashboard_readonly"
        )

    def test_dashboard_url_for_teacher_falls_back_to_overview(self):
        # Teachers without an admin role shouldn't be routed by this helper;
        # the login flow handles them separately. The fallback is safe.
        self.assertEqual(dashboard_url_for(self.teacher), "platform_admin:dashboard")


class RoleDashboardAccessTests(PlatformAdminTestMixin, TestCase):
    """Each tailored dashboard enforces the right role."""

    def test_control_root_redirects_finance_admin_to_finance(self):
        self.client.force_login(self.finance_admin)
        response = self.client.get(reverse("platform_admin:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("platform_admin:dashboard_finance"))

    def test_control_root_does_not_redirect_super_admin(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("platform_admin:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_academic_dashboard_renders_for_academic_admin(self):
        self.client.force_login(self.academic_admin)
        response = self.client.get(reverse("platform_admin:dashboard_academic"))
        self.assertEqual(response.status_code, 200)
        # Unique academic icon: book-open-check (pending courses card)
        self.assertIn(b"book-open-check", response.content)

    def test_academic_dashboard_forbidden_for_finance_admin(self):
        self.client.force_login(self.finance_admin)
        response = self.client.get(reverse("platform_admin:dashboard_academic"))
        self.assertEqual(response.status_code, 403)

    def test_finance_dashboard_renders_for_finance_admin(self):
        self.client.force_login(self.finance_admin)
        response = self.client.get(reverse("platform_admin:dashboard_finance"))
        self.assertEqual(response.status_code, 200)
        # Unique finance icon: alarm-clock (expiring-soon card)
        self.assertIn(b"alarm-clock", response.content)

    def test_finance_dashboard_forbidden_for_support_admin(self):
        self.client.force_login(self.support_admin)
        response = self.client.get(reverse("platform_admin:dashboard_finance"))
        self.assertEqual(response.status_code, 403)

    def test_support_dashboard_renders_for_support_admin(self):
        self.client.force_login(self.support_admin)
        response = self.client.get(reverse("platform_admin:dashboard_support"))
        self.assertEqual(response.status_code, 200)
        # Unique support icon: user-x (inactive-week card)
        self.assertIn(b"user-x", response.content)

    def test_ai_dashboard_renders_for_ai_admin(self):
        self.client.force_login(self.ai_admin)
        response = self.client.get(reverse("platform_admin:dashboard_ai"))
        self.assertEqual(response.status_code, 200)
        # Unique AI icon: git-branch (fallback-rate card)
        self.assertIn(b"git-branch", response.content)

    def test_ai_dashboard_forbidden_for_support_admin(self):
        self.client.force_login(self.support_admin)
        response = self.client.get(reverse("platform_admin:dashboard_ai"))
        self.assertEqual(response.status_code, 403)

    def test_readonly_dashboard_renders_for_readonly_admin(self):
        self.client.force_login(self.readonly_admin)
        response = self.client.get(reverse("platform_admin:dashboard_readonly"))
        self.assertEqual(response.status_code, 200)
        # Yellow read-only notice banner uses #FEF9C3 background
        self.assertIn(b"FEF9C3", response.content)

    def test_student_cannot_access_role_dashboards(self):
        self.client.force_login(self.student)
        for name in [
            "dashboard_academic",
            "dashboard_finance",
            "dashboard_support",
            "dashboard_ai",
            "dashboard_readonly",
        ]:
            response = self.client.get(reverse(f"platform_admin:{name}"))
            self.assertIn(response.status_code, (302, 403))
