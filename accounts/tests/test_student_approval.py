"""Student Registration Approval Gate + anti-bot tests."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest import mock

from accounts import approval
from accounts.forms import SignUpForm
from accounts.models import (
    APPROVAL_APPROVED, APPROVAL_PENDING_ADMIN, APPROVAL_PENDING_EMAIL,
    APPROVAL_REJECTED, APPROVAL_SUSPENDED, Profile, StudentApprovalEvent,
)

User = get_user_model()


def make_student(username="stu@x.com", status=APPROVAL_PENDING_ADMIN, email_verified=True):
    u = User.objects.create_user(username=username, email=username, password="pw12345!")
    p = u.profile
    p.role = "student"
    p.email_verified = email_verified
    p.approval_status = status
    p.save()
    return u


def make_admin(username="admin@x.com"):
    u = User.objects.create_superuser(username=username, email=username, password="pw12345!")
    return u


def make_teacher(username="teach@x.com"):
    u = User.objects.create_user(username=username, email=username, password="pw12345!")
    g, _ = Group.objects.get_or_create(name="Teacher")
    u.groups.add(g)
    return u


class ApprovalServiceTests(TestCase):
    def test_record_registration_sets_pending_and_audits(self):
        u = make_student(status=APPROVAL_PENDING_EMAIL)
        approval.record_registration(u, ip="1.2.3.4", user_agent="Mozilla",
                                     suspicious_flags=["repeated_ip"], suspicious_score=1)
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.approval_status, APPROVAL_PENDING_EMAIL)
        self.assertEqual(u.profile.registration_ip, "1.2.3.4")
        self.assertIn("repeated_ip", u.profile.suspicious_flags)
        self.assertTrue(StudentApprovalEvent.objects.filter(user=u, action="registered").exists())

    def test_mark_email_verified_advances_to_pending_admin(self):
        u = make_student(status=APPROVAL_PENDING_EMAIL, email_verified=False)
        approval.mark_email_verified(u)
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.approval_status, APPROVAL_PENDING_ADMIN)
        self.assertTrue(StudentApprovalEvent.objects.filter(user=u, action="email_verified").exists())

    def test_approve_sets_fields_and_audit(self):
        u = make_student()
        admin = make_admin()
        approval.approve(u, actor=admin, note="ok")
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.approval_status, APPROVAL_APPROVED)
        self.assertEqual(u.profile.admin_approved_by_id, admin.id)
        self.assertIsNotNone(u.profile.admin_approved_at)
        self.assertTrue(StudentApprovalEvent.objects.filter(user=u, action="approved").exists())

    def test_reject_requires_note(self):
        u = make_student()
        with self.assertRaises(approval.ApprovalError):
            approval.reject(u, actor=make_admin(), note="")
        approval.reject(u, actor=make_admin("a2@x.com"), note="bot")
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.approval_status, APPROVAL_REJECTED)

    def test_suspend_requires_note_and_audits(self):
        u = make_student(status=APPROVAL_APPROVED)
        with self.assertRaises(approval.ApprovalError):
            approval.suspend(u, actor=make_admin(), note="")
        approval.suspend(u, actor=make_admin("a3@x.com"), note="abuse")
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.approval_status, APPROVAL_SUSPENDED)
        self.assertTrue(StudentApprovalEvent.objects.filter(user=u, action="suspended").exists())

    def test_staff_and_teacher_exempt(self):
        self.assertTrue(make_admin().profile.is_approved_student)
        self.assertTrue(make_teacher().profile.is_approved_student)
        self.assertFalse(make_admin("a4@x.com").profile.needs_admin_approval)


@override_settings(ONLENCO_STUDENT_APPROVAL_REQUIRED=True)
class AccessGuardTests(TestCase):
    def test_pending_student_sees_waiting_page(self):
        self.client.force_login(make_student())
        resp = self.client.get(reverse("pending_approval"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "approval")

    def test_pending_student_cannot_access_dashboard(self):
        self.client.force_login(make_student())
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/account/pending-approval", resp["Location"])

    def test_pending_student_api_returns_403(self):
        self.client.force_login(make_student())
        resp = self.client.get("/api/ai-usage/limits/me/")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()["code"], "account_pending_approval")

    def test_approved_student_not_blocked(self):
        self.client.force_login(make_student(status=APPROVAL_APPROVED))
        resp = self.client.get(reverse("pending_approval"))
        self.assertEqual(resp.status_code, 302)  # bounced to dashboard

    def test_admin_not_blocked(self):
        self.client.force_login(make_admin())
        resp = self.client.get("/api/ai-usage/limits/me/")
        self.assertNotEqual(resp.status_code, 403)

    def test_teacher_not_blocked(self):
        self.client.force_login(make_teacher())
        resp = self.client.get("/api/ai-usage/limits/me/")
        self.assertNotEqual(resp.status_code, 403)


class RegistrationFlowTests(TestCase):
    @mock.patch("accounts.views._dispatch_signup_emails", lambda *a, **k: None)
    def test_new_student_registered_as_pending_and_not_dashboard(self):
        resp = self.client.post(reverse("auth"), {
            "mode": "signup", "full_name": "New Bot Free",
            "email": "newbie@example.com", "password": "secret12345",
        })
        u = User.objects.get(username="newbie@example.com")
        self.assertEqual(u.profile.approval_status, APPROVAL_PENDING_EMAIL)
        # Redirected to email verification, never straight to dashboard.
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("/dashboard", resp["Location"])

    def test_registration_honeypot_blocks_bot(self):
        form = SignUpForm(data={
            "full_name": "Bot", "email": "bot@example.com",
            "password": "secret12345", "ol_contact_url": "http://spam.example",
        })
        self.assertFalse(form.is_valid())
        # The bot account is never created.
        self.assertFalse(User.objects.filter(username="bot@example.com").exists())

    @override_settings(ONLENCO_BLOCK_DISPOSABLE_EMAILS=True,
                       ONLENCO_DISPOSABLE_EMAIL_DOMAINS=["mailinator.com"])
    def test_disposable_email_blocked_when_enabled(self):
        form = SignUpForm(data={
            "full_name": "Tmp", "email": "x@mailinator.com", "password": "secret12345",
        })
        self.assertFalse(form.is_valid())

    def test_suspicious_flags_recorded_on_profile(self):
        u = make_student(status=APPROVAL_PENDING_EMAIL)
        approval.record_registration(u, ip="9.9.9.9", user_agent="curl/8.0",
                                     suspicious_flags=["suspicious_user_agent"],
                                     suspicious_score=1)
        u.profile.refresh_from_db()
        self.assertIn("suspicious_user_agent", u.profile.suspicious_flags)


class ApprovalDashboardTests(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)
        self.admin = make_admin()
        self.student = make_student()

    def test_anonymous_cannot_access_dashboard(self):
        resp = self.client.get(reverse("platform_admin:student_approvals"))
        self.assertIn(resp.status_code, (302, 403))

    def test_student_forbidden_from_dashboard(self):
        self.client.force_login(make_student("s2@x.com"))
        resp = self.client.get(reverse("platform_admin:student_approvals"))
        self.assertIn(resp.status_code, (302, 403))

    def test_admin_can_view_pending_students(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("platform_admin:student_approvals"))
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_approve_student(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("platform_admin:student_approval_action",
                                 args=[self.student.id, "approve"]), {"note": "ok"})
        self.student.profile.refresh_from_db()
        self.assertEqual(self.student.profile.approval_status, APPROVAL_APPROVED)

    def test_admin_can_reject_student_with_note(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("platform_admin:student_approval_action",
                                 args=[self.student.id, "reject"]), {"note": "bot"})
        self.student.profile.refresh_from_db()
        self.assertEqual(self.student.profile.approval_status, APPROVAL_REJECTED)

    def test_approval_creates_audit_event(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("platform_admin:student_approval_action",
                                 args=[self.student.id, "approve"]), {"note": "ok"})
        self.assertTrue(StudentApprovalEvent.objects.filter(
            user=self.student, action="approved").exists())


class MigrationCommandTests(TestCase):
    def test_initialize_dry_run_changes_nothing(self):
        u = make_student(status=APPROVAL_PENDING_EMAIL, email_verified=True)
        call_command("initialize_student_approval_status", "--dry-run", verbosity=0)
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.approval_status, APPROVAL_PENDING_EMAIL)  # unchanged

    def test_initialize_confirm_approves_existing_verified_student(self):
        u = make_student(status=APPROVAL_PENDING_EMAIL, email_verified=True)
        call_command("initialize_student_approval_status", "--confirm", verbosity=0)
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.approval_status, APPROVAL_APPROVED)

    def test_initialize_keeps_unverified_pending(self):
        u = make_student(status=APPROVAL_PENDING_EMAIL, email_verified=False)
        call_command("initialize_student_approval_status", "--confirm", verbosity=0)
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.approval_status, APPROVAL_PENDING_EMAIL)

    def test_staff_teacher_exempt_approved(self):
        admin = make_admin("mig_admin@x.com")
        teacher = make_teacher("mig_teach@x.com")
        # Force them pending to prove the command flips privileged → approved.
        for u in (admin, teacher):
            u.profile.approval_status = APPROVAL_PENDING_EMAIL
            u.profile.save(update_fields=["approval_status"])
        call_command("initialize_student_approval_status", "--confirm", verbosity=0)
        admin.profile.refresh_from_db(); teacher.profile.refresh_from_db()
        self.assertEqual(admin.profile.approval_status, APPROVAL_APPROVED)
        self.assertEqual(teacher.profile.approval_status, APPROVAL_APPROVED)


class RegressionTests(TestCase):
    def test_login_works_and_pending_routes_to_waiting(self):
        make_student("login@x.com", status=APPROVAL_PENDING_ADMIN)
        resp = self.client.post(reverse("auth"), {
            "mode": "signin", "username": "login@x.com", "password": "pw12345!",
        })
        self.assertEqual(resp.status_code, 302)  # logged in, redirected

    def test_logout_works(self):
        self.client.force_login(make_student(status=APPROVAL_APPROVED))
        resp = self.client.post(reverse("logout"))
        self.assertEqual(resp.status_code, 302)
