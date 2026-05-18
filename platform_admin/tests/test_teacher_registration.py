from __future__ import annotations

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from platform_admin import permissions as perms
from platform_admin.models import PlatformAuditLog
from platform_admin.services import teacher_management_service

from .utils import PlatformAdminTestMixin


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class RegisterTeacherFlowTests(PlatformAdminTestMixin, TestCase):
    def test_form_get_renders_for_super_admin(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("platform_admin:teacher_create"))
        self.assertEqual(response.status_code, 200)

    def test_form_get_forbidden_for_support_admin(self):
        self.client.force_login(self.support_admin)
        response = self.client.get(reverse("platform_admin:teacher_create"))
        self.assertEqual(response.status_code, 403)

    def test_register_teacher_creates_user_and_sends_email(self):
        self.client.force_login(self.super_admin)
        mail.outbox = []
        response = self.client.post(
            reverse("platform_admin:teacher_create"),
            {
                "first_name": "Layla",
                "last_name": "Ahmed",
                "email": "layla@example.com",
                "email_confirm": "layla@example.com",
            },
        )
        self.assertEqual(response.status_code, 302)
        new_user = self.User.objects.get(email="layla@example.com")
        self.assertTrue(new_user.groups.filter(name=perms.GROUP_TEACHER).exists())
        self.assertTrue(new_user.profile.must_change_password)
        self.assertTrue(new_user.profile.email_verified)
        self.assertTrue(new_user.profile.onboarding_completed)
        self.assertEqual(len(mail.outbox), 1)
        # The plaintext temp password must appear in the email body.
        self.assertIn("layla@example.com", mail.outbox[0].body)

    def test_register_teacher_writes_audit_log(self):
        self.client.force_login(self.super_admin)
        self.client.post(
            reverse("platform_admin:teacher_create"),
            {
                "first_name": "Omar",
                "last_name": "Hassan",
                "email": "omar@example.com",
                "email_confirm": "omar@example.com",
            },
        )
        self.assertTrue(
            PlatformAuditLog.objects.filter(
                action_type="teacher.register",
                target_user__email="omar@example.com",
            ).exists()
        )

    def test_email_confirm_mismatch_rejected(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("platform_admin:teacher_create"),
            {
                "first_name": "A", "last_name": "B",
                "email": "ab@example.com", "email_confirm": "different@example.com",
            },
        )
        self.assertEqual(response.status_code, 200)  # re-renders the form
        self.assertFalse(self.User.objects.filter(email="ab@example.com").exists())

    def test_duplicate_email_rejected(self):
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("platform_admin:teacher_create"),
            {
                "first_name": "X", "last_name": "Y",
                "email": self.teacher.email, "email_confirm": self.teacher.email,
            },
        )
        self.assertEqual(response.status_code, 200)


class TempPasswordGenerationTests(TestCase):
    def test_temp_password_is_random_and_long(self):
        passwords = {teacher_management_service.generate_temporary_password() for _ in range(20)}
        self.assertEqual(len(passwords), 20, "passwords should be unique")
        for pwd in passwords:
            self.assertGreaterEqual(len(pwd), 12)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ForcePasswordChangeTests(PlatformAdminTestMixin, TestCase):
    def _register_teacher(self):
        self.client.force_login(self.super_admin)
        self.client.post(
            reverse("platform_admin:teacher_create"),
            {
                "first_name": "Noor", "last_name": "K",
                "email": "noor@example.com", "email_confirm": "noor@example.com",
            },
        )
        self.client.logout()
        return self.User.objects.get(email="noor@example.com")

    def test_teacher_redirected_to_change_password_on_login(self):
        teacher = self._register_teacher()
        self.client.force_login(teacher)
        response = self.client.get(reverse("teacher_portal:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("change_password"))

    def test_change_password_clears_flag_and_unblocks(self):
        teacher = self._register_teacher()
        self.client.force_login(teacher)
        # Find the welcome email by recipient — ``mail.outbox`` can hold
        # multiple messages (admin notifications also fire on register),
        # so indexing [0] would be order-dependent and flaky.
        welcome = next(
            (m for m in mail.outbox if teacher.email in (m.to or [])),
            None,
        )
        self.assertIsNotNone(welcome, "welcome email not found in outbox")
        temp_password = None
        for line in welcome.body.splitlines():
            line = line.strip()
            if line.startswith("Password:"):
                temp_password = line.split(":", 1)[1].strip()
                break
        self.assertIsNotNone(temp_password, "temp password missing from email body")
        response = self.client.post(
            reverse("change_password"),
            {
                "old_password": temp_password,
                "new_password1": "NewStr0ng!Pass$",
                "new_password2": "NewStr0ng!Pass$",
            },
        )
        self.assertEqual(response.status_code, 302)
        teacher.refresh_from_db()
        self.assertFalse(teacher.profile.must_change_password)
        # Now they can access the teacher dashboard without being redirected.
        response = self.client.get(reverse("teacher_portal:dashboard"))
        self.assertEqual(response.status_code, 200)

    def test_user_without_flag_not_redirected(self):
        self.client.force_login(self.super_admin)
        response = self.client.get(reverse("platform_admin:dashboard"))
        self.assertEqual(response.status_code, 200)
