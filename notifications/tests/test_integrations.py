"""Integration tests: confirm the right events are triggered from the
existing app flows (registration, payments, weekly assessment, AI failure).
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from notifications import constants as C
from notifications.models import EmailNotification, NotificationEvent

User = get_user_model()


@override_settings(AI_API_KEY="")
class IntegrationTests(TestCase):
    def test_register_user_triggers_welcome_and_admin_alert(self):
        from accounts.services import register_user

        # Have an admin to receive the fan-out
        User.objects.create_user(
            username="adm", email="adm@x", password="pw", is_staff=True
        )
        user = register_user(username="newbie", email="n@x", password="pw")

        events = NotificationEvent.objects.filter(
            event_type__in=[C.USER_REGISTERED, C.NEW_STUDENT_REGISTERED]
        )
        self.assertEqual(events.count(), 2)
        self.assertGreaterEqual(len(mail.outbox), 2)

    def test_payment_approval_arabic_email_body_for_ar_user(self):
        """An Arabic-preferred student must receive the Arabic body, not
        just the Arabic subject + English body."""
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from payments.models import PaymentMethodAccount, PaymentSubmission

        student = User.objects.create_user(
            username="arstud", email="arstud@x", password="pw",
        )
        # Force AR preference at the profile level (the source of truth).
        student.profile.preferred_language = "ar"
        student.profile.save(update_fields=["preferred_language"])
        admin = User.objects.create_user(
            username="adm_ar", email="adm_ar@x", password="pw", is_staff=True,
        )
        PaymentMethodAccount.objects.filter(method="bankak").update(is_active=True)
        png_file = SimpleUploadedFile(
            "x.png",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0eIDAT"
            b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa3'\x99\x9d\x00\x00\x00\x00IEND\xaeB`\x82",
            content_type="image/png",
        )
        sub = PaymentSubmission.objects.create(
            user=student, plan="monthly", method="bankak",
            transaction_reference="ar-r1", amount_sdg=30000, screenshot=png_file,
        )
        mail.outbox = []
        sub.approve(reviewer=admin)

        sent = EmailNotification.objects.filter(
            event__event_type=C.PAYMENT_APPROVED,
            recipient_email="arstud@x",
            status=C.STATUS_SENT,
        )
        self.assertEqual(sent.count(), 1)
        record = sent.first()
        self.assertEqual(
            record.language, "ar",
            f"EmailNotification.language should be 'ar', got {record.language!r}",
        )
        # The subject must contain Arabic glyphs (Arabic Unicode block).
        import re
        self.assertRegex(
            record.subject, r"[؀-ۿ]",
            "Subject must contain Arabic characters",
        )
        # The rendered HTML body must also contain Arabic — not just the subject.
        ar_messages = [m for m in mail.outbox if m.to == ["arstud@x"]]
        self.assertEqual(len(ar_messages), 1)
        rendered = ""
        for content, mime in (ar_messages[0].alternatives or []):
            if "html" in mime:
                rendered = content
                break
        if not rendered:
            rendered = ar_messages[0].body or ""
        self.assertRegex(
            rendered, r"[؀-ۿ]",
            "Email HTML body must contain Arabic for an Arabic-preferred user",
        )

    def test_payment_approval_emails_student(self):
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        from payments.models import PaymentMethodAccount, PaymentSubmission

        student = User.objects.create_user(username="stud", email="stud@x", password="pw")
        admin = User.objects.create_user(username="adm2", email="adm2@x", password="pw", is_staff=True)
        PaymentMethodAccount.objects.filter(method="bankak").update(is_active=True)
        png_file = SimpleUploadedFile(
            "x.png",
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\x0eIDAT"
            b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa3'\x99\x9d\x00\x00\x00\x00IEND\xaeB`\x82",
            content_type="image/png",
        )
        sub = PaymentSubmission.objects.create(
            user=student, plan="monthly", method="bankak",
            transaction_reference="r1", amount_sdg=30000, screenshot=png_file,
        )
        sub.approve(reviewer=admin)
        approved = NotificationEvent.objects.filter(event_type=C.PAYMENT_APPROVED, user=student)
        self.assertEqual(approved.count(), 1)
        sent = EmailNotification.objects.filter(
            event__event_type=C.PAYMENT_APPROVED, status=C.STATUS_SENT
        )
        self.assertEqual(sent.count(), 1)
        self.assertEqual(sent.first().recipient_email, "stud@x")

    def test_weekly_assessment_trigger_sends_via_notification_service(self):
        from learning_core.services.weekly_assessment import maybe_trigger
        from lessons.models import Lesson, LessonProgress
        from django.utils import timezone

        u = User.objects.create_user(username="wky", email="wky@x", password="pw")
        for i in range(3):
            les = Lesson.objects.create(
                title=f"L{i}", skill="reading", level="A2", duration_minutes=10
            )
            LessonProgress.objects.create(
                user=u, lesson=les, video_completed=True, quiz_passed=True,
                completed_at=timezone.now(),
            )
        wa = maybe_trigger(u)
        self.assertIsNotNone(wa)
        ev = NotificationEvent.objects.filter(
            event_type=C.WEEKLY_ASSESSMENT_AVAILABLE, user=u
        ).first()
        self.assertIsNotNone(ev)
        # maybe_trigger also generates exercises, which fires its own email.
        self.assertGreaterEqual(len(mail.outbox), 1)
        self.assertTrue(
            any("/dashboard/weekly/" in msg.body for msg in mail.outbox),
            "Expected the weekly_assessment_available email to contain the weekly link",
        )

    def test_ai_failure_logs_admin_event(self):
        # Create an admin so the fan-out has somewhere to land
        admin = User.objects.create_user(
            username="adm3", email="adm3@x", password="pw", is_staff=True
        )
        from core.services.ai_usage import log_usage
        log_usage(
            None, "tutor", model="m", success=False, error_message="boom",
        )
        ev = NotificationEvent.objects.filter(event_type=C.AI_FAILURE).first()
        self.assertIsNotNone(ev)
        sent = EmailNotification.objects.filter(
            event=ev, status=C.STATUS_SENT, recipient_email="adm3@x"
        )
        self.assertEqual(sent.count(), 1)
