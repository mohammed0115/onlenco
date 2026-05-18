"""Admin actions for the 'verification email didn't arrive' workflow."""
from __future__ import annotations

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from platform_admin.models import PlatformAuditLog

from .utils import PlatformAdminTestMixin


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ManualEmailVerifyTests(PlatformAdminTestMixin, TestCase):
    def test_super_admin_can_mark_email_verified(self):
        self.student.profile.email_verified = False
        self.student.profile.save(update_fields=["email_verified"])
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("platform_admin:student_action", args=[self.student.pk, "verify-email"]),
        )
        self.assertEqual(response.status_code, 302)
        self.student.profile.refresh_from_db()
        self.assertTrue(self.student.profile.email_verified)
        self.assertTrue(
            PlatformAuditLog.objects.filter(
                action_type="student.email_verify_manual",
                target_user=self.student,
            ).exists()
        )

    def test_support_admin_can_mark_email_verified(self):
        # Support admin has CAP_NOTIFICATIONS_MANAGE — also allowed.
        self.student.profile.email_verified = False
        self.student.profile.save(update_fields=["email_verified"])
        self.client.force_login(self.support_admin)
        response = self.client.post(
            reverse("platform_admin:student_action", args=[self.student.pk, "verify-email"]),
        )
        self.assertEqual(response.status_code, 302)
        self.student.profile.refresh_from_db()
        self.assertTrue(self.student.profile.email_verified)

    def test_finance_admin_cannot_mark_email_verified(self):
        # Finance has no STUDENTS_MANAGE / NOTIFICATIONS_MANAGE.
        self.student.profile.email_verified = False
        self.student.profile.save(update_fields=["email_verified"])
        self.client.force_login(self.finance_admin)
        response = self.client.post(
            reverse("platform_admin:student_action", args=[self.student.pk, "verify-email"]),
        )
        self.assertEqual(response.status_code, 403)

    def test_already_verified_is_noop(self):
        self.student.profile.email_verified = True
        self.student.profile.save(update_fields=["email_verified"])
        self.client.force_login(self.super_admin)
        response = self.client.post(
            reverse("platform_admin:student_action", args=[self.student.pk, "verify-email"]),
        )
        self.assertEqual(response.status_code, 302)
        # No audit row created when there's nothing to do.
        self.assertFalse(
            PlatformAuditLog.objects.filter(
                action_type="student.email_verify_manual",
                target_user=self.student,
            ).exists()
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class ResendVerificationTests(PlatformAdminTestMixin, TestCase):
    def test_super_admin_can_resend_verification(self):
        self.client.force_login(self.super_admin)
        mail.outbox = []
        response = self.client.post(
            reverse("platform_admin:student_action", args=[self.student.pk, "resend-verification"]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertIn(self.student.email, mail.outbox[0].to)
        self.assertTrue(
            PlatformAuditLog.objects.filter(
                action_type="student.verification_resend",
                target_user=self.student,
            ).exists()
        )

    def test_resend_with_no_email_returns_warning(self):
        self.student.email = ""
        self.student.save(update_fields=["email"])
        self.client.force_login(self.super_admin)
        mail.outbox = []
        response = self.client.post(
            reverse("platform_admin:student_action", args=[self.student.pk, "resend-verification"]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 0)

    def test_finance_admin_cannot_resend(self):
        self.client.force_login(self.finance_admin)
        response = self.client.post(
            reverse("platform_admin:student_action", args=[self.student.pk, "resend-verification"]),
        )
        self.assertEqual(response.status_code, 403)


class EmailSmtpCheckCommandTests(TestCase):
    def test_command_runs_without_args(self):
        from io import StringIO
        from django.core.management import call_command
        out = StringIO()
        call_command("email_smtp_check", stdout=out)
        output = out.getvalue()
        self.assertIn("Email config", output)
        self.assertIn("Deliverability tips", output)
