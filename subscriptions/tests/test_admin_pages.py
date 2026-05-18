from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from platform_admin import permissions as perms
from platform_admin.models import PlatformAuditLog
from subscriptions.models import SubscriptionPlan, UserSubscription
from subscriptions.services import subscription_service


User = get_user_model()


def _make_admin(email: str, group_name: str):
    user = User.objects.create_user(username=email, email=email, password="pw", is_staff=True)
    user.profile.role = "admin"
    user.profile.save(update_fields=["role"])
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


class PlansListAccessTests(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)

    def test_super_admin_can_view_plans(self):
        user = User.objects.create_user(
            username="root@example.com", email="root@example.com",
            password="pw", is_staff=True, is_superuser=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("platform_admin:plans"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "basic_10m")

    def test_finance_admin_can_view_plans(self):
        user = _make_admin("fin@example.com", perms.GROUP_FINANCE_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse("platform_admin:plans"))
        self.assertEqual(response.status_code, 200)

    def test_support_admin_cannot_view_plans(self):
        user = _make_admin("sup@example.com", perms.GROUP_SUPPORT_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse("platform_admin:plans"))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_view_plans(self):
        user = User.objects.create_user(username="stu@example.com", email="stu@example.com", password="pw")
        self.client.force_login(user)
        response = self.client.get(reverse("platform_admin:plans"))
        self.assertIn(response.status_code, (302, 403))


class PlanCRUDTests(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)
        self.admin = _make_admin("super@example.com", perms.GROUP_SUPER_ADMIN)
        self.client.force_login(self.admin)

    def test_create_plan(self):
        payload = {
            "code": "premium_60m",
            "name_en": "Premium",
            "name_ar": "بريميوم",
            "description_en": "60 minutes",
            "description_ar": "",
            "price_sdg": 300000,
            "currency": "SDG",
            "billing_cycle": "monthly",
            "ai_tutor_daily_minutes": 60,
            "library_audio_daily_minutes": 90,
            "is_active": "on",
            "sort_order": 50,
        }
        response = self.client.post(reverse("platform_admin:plan_create"), payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SubscriptionPlan.objects.filter(code="premium_60m").exists())
        self.assertTrue(
            PlatformAuditLog.objects.filter(
                action_type="plan.create", object_id="%d" % SubscriptionPlan.objects.get(code="premium_60m").pk,
            ).exists()
        )

    def test_edit_plan_updates_price_and_minutes(self):
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        payload = {
            "code": plan.code,
            "name_en": plan.name_en,
            "name_ar": plan.name_ar,
            "description_en": plan.description_en,
            "description_ar": plan.description_ar,
            "price_sdg": 75000,  # was 50000
            "currency": plan.currency,
            "billing_cycle": plan.billing_cycle,
            "ai_tutor_daily_minutes": 12,  # was 10
            "library_audio_daily_minutes": plan.library_audio_daily_minutes,
            "is_active": "on",
            "sort_order": plan.sort_order,
        }
        response = self.client.post(reverse("platform_admin:plan_edit", args=[plan.pk]), payload)
        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.price_sdg, 75000)
        self.assertEqual(plan.ai_tutor_daily_minutes, 12)
        self.assertTrue(
            PlatformAuditLog.objects.filter(action_type="plan.update", object_id=str(plan.pk)).exists()
        )

    def test_delete_plan_without_subscriptions(self):
        plan = SubscriptionPlan.objects.create(
            code="throwaway", name_en="X", name_ar="X", price_sdg=0,
            ai_tutor_daily_minutes=1, library_audio_daily_minutes=1,
        )
        pk = plan.pk
        response = self.client.post(reverse("platform_admin:plan_delete", args=[pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SubscriptionPlan.objects.filter(pk=pk).exists())

    def test_delete_plan_with_subscriptions_blocked(self):
        plan = SubscriptionPlan.objects.get(code="basic_10m")
        learner = User.objects.create_user(username="l@example.com", email="l@example.com", password="pw")
        subscription_service.activate_subscription(user=learner, plan=plan, duration_days=30)
        response = self.client.post(reverse("platform_admin:plan_delete", args=[plan.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SubscriptionPlan.objects.filter(pk=plan.pk).exists())


class PlansNavigationTests(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)

    def test_finance_admin_sees_plans_in_nav(self):
        user = _make_admin("finance@example.com", perms.GROUP_FINANCE_ADMIN)
        nav = perms.nav_items_for(user)
        url_names = {item["url_name"] for item in nav}
        self.assertIn("platform_admin:plans", url_names)

    def test_support_admin_does_not_see_plans_in_nav(self):
        user = _make_admin("sup2@example.com", perms.GROUP_SUPPORT_ADMIN)
        nav = perms.nav_items_for(user)
        url_names = {item["url_name"] for item in nav}
        self.assertNotIn("platform_admin:plans", url_names)
