"""Verify the motivation messages API humanizes raw stored text before
returning it to clients."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from motivation import constants as C
from motivation.models import MotivationMessage

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class MotivationMessageApiHumanizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="m@x.com", email="m@x.com", password="pw"
        )
        self.client.login(username="m@x.com", password="pw")

    def _get_message(self):
        resp = self.client.get(reverse("motivation_api:messages"))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        results = data["results"] if isinstance(data, dict) and "results" in data else data
        return results[0]

    def test_snake_case_in_stored_message_humanized_in_api(self):
        MotivationMessage.objects.create(
            user=self.user,
            message_type=C.MSG_ENCOURAGEMENT,
            title="weekly_assessment_available",
            message="Your theta_score is up.",
            language="en",
        )
        m = self._get_message()
        self.assertEqual(m["title"], "Weekly assessment is available")
        self.assertNotIn("theta_score", m["message"])
        self.assertIn("learning ability score", m["message"])

    def test_arabic_stored_message_uses_arabic_glossary(self):
        MotivationMessage.objects.create(
            user=self.user,
            message_type=C.MSG_ACHIEVEMENT,
            title="payment_approved",
            message="حالة: payment_approved",
            language="ar",
        )
        m = self._get_message()
        self.assertEqual(m["title"], "تم قبول الدفع")
        self.assertIn("تم قبول الدفع", m["message"])
        self.assertNotIn("payment_approved", m["message"])
