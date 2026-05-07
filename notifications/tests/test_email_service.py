from unittest.mock import patch

from django.test import TestCase

from notifications.services.email_service import EmailService


class EmailServiceTests(TestCase):
    def setUp(self):
        self.svc = EmailService()

    def test_send_to_outbox(self):
        from django.core import mail

        result = self.svc.send_email(
            recipient_email="x@y.com",
            subject="Hi",
            html_body="<p>hello</p>",
        )
        self.assertTrue(result.success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Hi")
        # Default plain-text fallback strips HTML
        self.assertIn("hello", mail.outbox[0].body)

    def test_no_recipient_returns_failure(self):
        result = self.svc.send_email(recipient_email="", subject="x", html_body="x")
        self.assertFalse(result.success)
        self.assertIn("no recipient", result.error_message)

    def test_smtp_exception_returns_failure(self):
        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=RuntimeError("boom"),
        ):
            result = self.svc.send_email("x@y", "s", "<p>b</p>")
        self.assertFalse(result.success)
        self.assertIn("boom", result.error_message)
