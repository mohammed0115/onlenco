from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase

from notifications import constants as C
from notifications.models import EmailNotification, NotificationEvent
from notifications.services.notification_service import NotificationService

User = get_user_model()


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.svc = NotificationService()
        self.user = User.objects.create_user(
            username="ali", email="ali@x.com", password="pw"
        )

    def test_trigger_creates_event_and_sends_email(self):
        ev = self.svc.trigger(
            C.USER_REGISTERED, user=self.user, payload={"cta_url": "/dashboard/"}
        )
        ev.refresh_from_db()
        self.assertEqual(ev.status, C.STATUS_PROCESSED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(EmailNotification.objects.filter(event=ev).count(), 1)
        en = EmailNotification.objects.get(event=ev)
        self.assertEqual(en.status, C.STATUS_SENT)

    def test_trigger_skips_when_no_email(self):
        u = User.objects.create_user(username="noemail", password="pw")
        ev = self.svc.trigger(C.USER_REGISTERED, user=u)
        en = EmailNotification.objects.get(event=ev)
        self.assertEqual(en.status, C.STATUS_SKIPPED)
        self.assertEqual(len(mail.outbox), 0)

    def test_dedup_within_window(self):
        self.svc.trigger(C.LESSON_COMPLETED, user=self.user)
        self.svc.trigger(C.LESSON_COMPLETED, user=self.user)
        sent = EmailNotification.objects.filter(
            event__event_type=C.LESSON_COMPLETED, status=C.STATUS_SENT
        ).count()
        skipped = EmailNotification.objects.filter(
            event__event_type=C.LESSON_COMPLETED, status=C.STATUS_SKIPPED
        ).count()
        self.assertEqual(sent, 1)
        self.assertEqual(skipped, 1)

    def test_failed_email_records_error(self):
        with patch(
            "notifications.services.email_service.EmailMultiAlternatives.send",
            side_effect=RuntimeError("smtp down"),
        ):
            ev = self.svc.trigger(C.USER_REGISTERED, user=self.user)
        en = EmailNotification.objects.get(event=ev)
        self.assertEqual(en.status, C.STATUS_FAILED)
        self.assertIn("smtp down", en.error_message)

    def test_retry_failed_email(self):
        with patch(
            "notifications.services.email_service.EmailMultiAlternatives.send",
            side_effect=RuntimeError("temp"),
        ):
            ev = self.svc.trigger(C.USER_REGISTERED, user=self.user)
        en = EmailNotification.objects.get(event=ev)
        self.assertEqual(en.status, C.STATUS_FAILED)
        # Now retry — it should send.
        self.svc.retry_failed_email(en)
        en.refresh_from_db()
        self.assertEqual(en.status, C.STATUS_SENT)
        self.assertEqual(en.attempts_count, 2)

    def test_notify_admins_targets_staff_only(self):
        admin = User.objects.create_user(
            username="adm", email="adm@x", password="pw", is_staff=True
        )
        self.svc.notify_admins(C.NEW_PAYMENT_PENDING, payload={"plan": "monthly"})
        admin_emails = EmailNotification.objects.filter(
            event__event_type=C.NEW_PAYMENT_PENDING, status=C.STATUS_SENT
        )
        self.assertEqual(admin_emails.count(), 1)
        self.assertEqual(admin_emails.first().recipient_email, "adm@x")
