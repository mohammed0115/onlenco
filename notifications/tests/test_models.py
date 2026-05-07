from django.contrib.auth import get_user_model
from django.test import TestCase

from notifications.models import (
    EmailNotification,
    NotificationEvent,
    NotificationPreference,
    NotificationTemplate,
)

User = get_user_model()


class NotificationModelsTests(TestCase):
    def test_event_create_and_str(self):
        u = User.objects.create_user(username="m1", email="a@b", password="pw")
        ev = NotificationEvent.objects.create(
            event_type="user_registered", user=u, payload={"x": 1}
        )
        self.assertIn("user_registered", str(ev))
        self.assertEqual(ev.status, "pending")

    def test_email_notification_log(self):
        u = User.objects.create_user(username="m2", email="b@b", password="pw")
        ev = NotificationEvent.objects.create(event_type="welcome", user=u)
        en = EmailNotification.objects.create(
            event=ev,
            user=u,
            recipient_email="b@b",
            subject="Hi",
            template_name="welcome.html",
            language="en",
        )
        self.assertEqual(en.status, "pending")
        self.assertEqual(en.attempts_count, 0)

    def test_preference_one_per_user(self):
        u = User.objects.create_user(username="m3", email="c@c", password="pw")
        NotificationPreference.objects.create(user=u)
        with self.assertRaises(Exception):
            NotificationPreference.objects.create(user=u)

    def test_template_unique_per_event_language(self):
        NotificationTemplate.objects.create(
            event_type="welcome", language="en", subject="x", template_name="welcome.html"
        )
        with self.assertRaises(Exception):
            NotificationTemplate.objects.create(
                event_type="welcome", language="en", subject="y", template_name="other.html"
            )
