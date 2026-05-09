from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class DashboardViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dee", password="pw")

    def test_dashboard_renders_for_new_user(self):
        # New users default to Arabic; pin to English for the label assertion.
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)
        r = self.client.get(reverse("dashboard"), HTTP_ACCEPT_LANGUAGE="en")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "My English level")  # English label

    def test_dashboard_renders_with_cefr_level(self):
        self.user.profile.cefr_level = "A2"
        self.user.profile.save()
        self.client.force_login(self.user)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "A2")
