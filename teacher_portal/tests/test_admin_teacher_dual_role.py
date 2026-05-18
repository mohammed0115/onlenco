"""Admin+Teacher dual-role flow tests.

The same user can hold an admin role (Academic / Platform / etc.) AND the
Teacher role. They must NOT be treated as a student: no onboarding, no
placement, no student dashboard redirect.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts import onboarding as onboarding_lib
from platform_admin import permissions as control_perms
from teacher_portal.services.role_service import (
    ROLE_STUDENT,
    ROLE_TEACHER,
    RoleService,
)


User = get_user_model()


def _make_user(email, **kwargs):
    user = User.objects.create_user(username=email, email=email, password="pw", **kwargs)
    user.profile.email_verified = True
    user.profile.save(update_fields=["email_verified"])
    return user


def _give_group(user, group_name):
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


class RoleServiceDualRoleTests(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)

    def test_admin_plus_teacher_is_not_student(self):
        user = _make_user("admin_teacher@example.com")
        _give_group(user, control_perms.GROUP_ACADEMIC_ADMIN)
        _give_group(user, control_perms.GROUP_TEACHER)
        self.assertFalse(RoleService.user_has_role(user, ROLE_STUDENT))
        self.assertTrue(RoleService.is_admin_user(user))
        self.assertTrue(RoleService.is_teacher_user(user))

    def test_admin_only_is_not_student(self):
        user = _make_user("admin_only@example.com")
        _give_group(user, control_perms.GROUP_FINANCE_ADMIN)
        self.assertFalse(RoleService.user_has_role(user, ROLE_STUDENT))
        self.assertTrue(RoleService.is_admin_user(user))
        self.assertFalse(RoleService.is_teacher_user(user))

    def test_teacher_only_with_default_profile_is_not_student(self):
        # Teachers without explicit student role: default profile.role is
        # "student" but the Teacher group flips them out of the student bucket.
        user = _make_user("teacher_only@example.com")
        _give_group(user, control_perms.GROUP_TEACHER)
        self.assertFalse(RoleService.user_has_role(user, ROLE_STUDENT))
        self.assertTrue(RoleService.is_teacher_user(user))

    def test_plain_student_is_student(self):
        user = _make_user("student@example.com")
        self.assertTrue(RoleService.user_has_role(user, ROLE_STUDENT))
        self.assertFalse(RoleService.is_admin_user(user))
        self.assertFalse(RoleService.is_teacher_user(user))

    def test_default_landing_admin_teacher_goes_to_control(self):
        user = _make_user("a_t_landing@example.com")
        _give_group(user, control_perms.GROUP_ACADEMIC_ADMIN)
        _give_group(user, control_perms.GROUP_TEACHER)
        # academic admin → academic dashboard
        self.assertEqual(
            RoleService.get_default_landing_page(user),
            "platform_admin:dashboard_academic",
        )

    def test_default_landing_teacher_only_goes_to_teacher_portal(self):
        user = _make_user("t_only_landing@example.com")
        _give_group(user, control_perms.GROUP_TEACHER)
        self.assertEqual(
            RoleService.get_default_landing_page(user), "teacher_portal:dashboard"
        )

    def test_default_landing_student_goes_to_dashboard(self):
        user = _make_user("s_landing@example.com")
        self.assertEqual(RoleService.get_default_landing_page(user), "dashboard")

    def test_available_staff_modes_admin_teacher_has_both(self):
        user = _make_user("modes_at@example.com")
        _give_group(user, control_perms.GROUP_PLATFORM_ADMIN)
        _give_group(user, control_perms.GROUP_TEACHER)
        modes = [m["mode"] for m in RoleService.available_staff_modes(user)]
        self.assertEqual(modes, ["control", "teacher"])

    def test_available_staff_modes_teacher_only(self):
        user = _make_user("modes_t@example.com")
        _give_group(user, control_perms.GROUP_TEACHER)
        modes = [m["mode"] for m in RoleService.available_staff_modes(user)]
        self.assertEqual(modes, ["teacher"])

    def test_available_staff_modes_student_only_is_empty(self):
        user = _make_user("modes_s@example.com")
        self.assertEqual(RoleService.available_staff_modes(user), [])


class OnboardingSkipTests(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)

    def test_admin_teacher_skips_onboarding(self):
        user = _make_user("admin_t_onb@example.com")
        _give_group(user, control_perms.GROUP_ACADEMIC_ADMIN)
        _give_group(user, control_perms.GROUP_TEACHER)
        # Even with onboarding_completed=False, admin/teacher bypasses it.
        user.profile.onboarding_completed = False
        user.profile.save(update_fields=["onboarding_completed"])
        self.assertIsNone(onboarding_lib.next_url_for(user))

    def test_teacher_only_skips_onboarding(self):
        user = _make_user("t_onb@example.com")
        _give_group(user, control_perms.GROUP_TEACHER)
        user.profile.onboarding_completed = False
        user.profile.save(update_fields=["onboarding_completed"])
        self.assertIsNone(onboarding_lib.next_url_for(user))

    def test_admin_only_skips_onboarding(self):
        user = _make_user("a_onb@example.com")
        _give_group(user, control_perms.GROUP_FINANCE_ADMIN)
        user.profile.onboarding_completed = False
        user.profile.save(update_fields=["onboarding_completed"])
        self.assertIsNone(onboarding_lib.next_url_for(user))

    def test_student_still_gets_onboarding(self):
        user = _make_user("s_onb@example.com")
        user.profile.onboarding_completed = False
        user.profile.save(update_fields=["onboarding_completed"])
        self.assertEqual(onboarding_lib.next_url_for(user), reverse("onboarding_choice"))


class SwitchStaffModeTests(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)

    def test_admin_teacher_can_switch_to_control(self):
        user = _make_user("sw_at@example.com", is_staff=True)
        _give_group(user, control_perms.GROUP_PLATFORM_ADMIN)
        _give_group(user, control_perms.GROUP_TEACHER)
        self.client.force_login(user)
        response = self.client.get(reverse("teacher_portal:switch_staff_mode", args=["control"]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("platform_admin:dashboard"))
        self.assertEqual(self.client.session["active_staff_mode"], "control")

    def test_admin_teacher_can_switch_to_teacher(self):
        user = _make_user("sw_at2@example.com", is_staff=True)
        _give_group(user, control_perms.GROUP_PLATFORM_ADMIN)
        _give_group(user, control_perms.GROUP_TEACHER)
        self.client.force_login(user)
        response = self.client.get(reverse("teacher_portal:switch_staff_mode", args=["teacher"]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("teacher_portal:dashboard"))
        self.assertEqual(self.client.session["active_staff_mode"], "teacher")

    def test_teacher_only_cannot_switch_to_control(self):
        user = _make_user("sw_t@example.com")
        _give_group(user, control_perms.GROUP_TEACHER)
        self.client.force_login(user)
        response = self.client.get(reverse("teacher_portal:switch_staff_mode", args=["control"]))
        self.assertEqual(response.status_code, 403)

    def test_admin_only_without_teacher_cannot_switch_to_teacher(self):
        user = _make_user("sw_a@example.com", is_staff=True)
        _give_group(user, control_perms.GROUP_FINANCE_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse("teacher_portal:switch_staff_mode", args=["teacher"]))
        self.assertEqual(response.status_code, 403)

    def test_unknown_mode_404(self):
        user = _make_user("sw_unknown@example.com", is_staff=True)
        _give_group(user, control_perms.GROUP_PLATFORM_ADMIN)
        self.client.force_login(user)
        response = self.client.get(reverse("teacher_portal:switch_staff_mode", args=["student"]))
        self.assertEqual(response.status_code, 404)
