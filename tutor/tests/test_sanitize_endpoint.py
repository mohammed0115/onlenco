"""Integration test: tutor sanitiser endpoint cleans speech text."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class SanitizeEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="san@x.com", email="san@x.com", password="pw"
        )
        prof = self.user.profile
        prof.subscription_status = "active"
        prof.subscription_expires_at = timezone.now() + timezone.timedelta(days=30)
        prof.save()
        self.client.login(username="san@x.com", password="pw")

    def test_endpoint_strips_snake_case_and_url(self):
        resp = self.client.post(
            reverse("tutor_sanitize"),
            {
                "text": "Visit https://x.com about your weekly_assessment_available status.",
                "language": "en",
            },
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertNotIn("https://", body["text"])
        self.assertNotIn("weekly_assessment_available", body["text"])
        self.assertIn("Weekly assessment", body["text"])

    def test_endpoint_arabic(self):
        resp = self.client.post(
            reverse("tutor_sanitize"),
            {"text": "حالة: payment_approved", "language": "ar"},
        )
        body = resp.json()
        self.assertEqual(body["language"], "ar")
        self.assertIn("تم قبول الدفع", body["text"])

    def test_anonymous_blocked(self):
        self.client.logout()
        resp = self.client.post(
            reverse("tutor_sanitize"),
            {"text": "anything", "language": "en"},
        )
        # login_required → 302 redirect to /auth/
        self.assertEqual(resp.status_code, 302)
