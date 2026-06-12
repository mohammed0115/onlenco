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


class DashboardRedesignTests(TestCase):
    """19.0-UX redesign: key sections + mobile bottom nav are present."""

    def setUp(self):
        self.user = User.objects.create_user(username="ux", password="pw")
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)
        self.resp = self.client.get(reverse("dashboard"), HTTP_ACCEPT_LANGUAGE="en")

    def test_status_ok(self):
        self.assertEqual(self.resp.status_code, 200)

    def test_today_tasks_section_present(self):
        self.assertContains(self.resp, "Today’s tasks")

    def test_ai_tutor_card_present(self):
        self.assertContains(self.resp, "AI Tutor")
        # Start-speaking action links to the live voice call.
        self.assertContains(self.resp, reverse("tutor_voice_call_quick"))

    def test_skill_progress_four_skills(self):
        for skill in ("Listening", "Speaking", "Reading", "Writing"):
            self.assertContains(self.resp, skill)

    def test_library_card_present(self):
        self.assertContains(self.resp, reverse("library"))

    def test_mobile_bottom_nav_present(self):
        self.assertContains(self.resp, "onl-bottomnav")
        self.assertContains(self.resp, 'aria-current="page"')
        for url_name in ("dashboard", "exam_daily", "tutor", "profile"):
            self.assertContains(self.resp, reverse(url_name))

    def test_no_inline_gradient_style_attrs(self):
        # The redesign moved gradients into a <style> block (gradient classes),
        # so no per-card inline linear-gradient style attributes remain.
        self.assertNotContains(self.resp, 'style="background: linear-gradient')
