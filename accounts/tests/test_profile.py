"""Tests for the user-facing Profile / Settings page.

Covers:
  * GET renders for an authenticated user.
  * Anonymous users are redirected to login.
  * Page contains the "Take placement" CTA before placement, and the
    "Retake placement" CTA afterwards.
  * Posting `preferred_language=en|ar` updates the profile + flashes
    a success message.
  * Invalid language is rejected without changing state.
  * Retake POST goes through `placement_retake` and reaches the
    placement page (audit item #14).
  * The header's Profile link is shown only when authenticated.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="prof@x.com", email="prof@x.com", password="pw",
        )
        self.user.profile.full_name = "Test Student"
        self.user.profile.email_verified = True
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=[
            "full_name", "email_verified", "preferred_language",
        ])

    # ---- Auth gating -----------------------------------------------

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(reverse("profile"))
        self.assertEqual(resp.status_code, 302)
        # login_required → /auth/?next=/auth/profile/
        self.assertIn("/auth/", resp.url)

    def test_authenticated_user_sees_page(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("profile"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Test Student")
        self.assertContains(resp, "prof@x.com")

    # ---- Placement CTA: take vs retake -----------------------------

    def test_shows_take_placement_when_not_yet_completed(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("profile"))
        self.assertContains(resp, 'data-testid="profile-take-placement"')
        self.assertNotContains(resp, 'data-testid="profile-retake-placement"')

    def test_shows_retake_placement_after_completion(self):
        self.user.profile.placement_completed = True
        self.user.profile.cefr_level = "B1"
        self.user.profile.save(update_fields=[
            "placement_completed", "cefr_level",
        ])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("profile"))
        self.assertContains(resp, 'data-testid="profile-retake-placement"')
        self.assertNotContains(resp, 'data-testid="profile-take-placement"')

    def test_retake_button_action_goes_to_placement_retake(self):
        # Lock in the URL — if someone refactors `placement_retake` away,
        # this catches it.
        self.user.profile.placement_completed = True
        self.user.profile.save(update_fields=["placement_completed"])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("profile"))
        self.assertContains(resp, f'action="{reverse("placement_retake")}"')

    def test_retake_round_trip_takes_user_to_placement(self):
        self.user.profile.placement_completed = True
        self.user.profile.save(update_fields=["placement_completed"])
        self.client.force_login(self.user)
        # The retake POST sets a session flag and redirects to placement.
        resp = self.client.post(reverse("placement_retake"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("placement"))

    # ---- Language preference --------------------------------------

    def test_post_preferred_language_updates_profile(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("profile"), {"preferred_language": "ar"})
        self.assertRedirects(resp, reverse("profile"),
                             fetch_redirect_response=False)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.preferred_language, "ar")

    def test_post_invalid_language_is_rejected(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse("profile"), {"preferred_language": "fr"})
        self.assertRedirects(resp, reverse("profile"),
                             fetch_redirect_response=False)
        self.user.profile.refresh_from_db()
        # Unchanged.
        self.assertEqual(self.user.profile.preferred_language, "en")

    def test_lang_buttons_show_active_state(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("profile"))
        # The English button is active because preferred_language="en".
        self.assertContains(
            resp,
            'name="preferred_language" value="en"\n                class="lang-button active"',
        )

    # ---- Localisation ---------------------------------------------

    def test_arabic_render(self):
        self.user.profile.preferred_language = "ar"
        self.user.profile.save(update_fields=["preferred_language"])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("profile"))
        self.assertContains(resp, "الحساب والإعدادات")
        self.assertContains(resp, "اللغة")

    def test_english_render(self):
        self.client.force_login(self.user)  # already 'en'
        resp = self.client.get(reverse("profile"))
        self.assertContains(resp, "Profile & settings")
        self.assertContains(resp, "Manage your account")
        self.assertContains(resp, "Language")

    # ---- Header link ----------------------------------------------

    def test_header_profile_link_present_when_authenticated(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("dashboard"))
        self.assertContains(resp, 'data-testid="header-profile-link"')
        self.assertContains(resp, reverse("profile"))


@override_settings(AXES_ENABLED=False)
class ProfileLearningStateTests(TestCase):
    """The Learning-level card must show CEFR + onboarding-path
    pills correctly for both onboarding routes."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="ls@x.com", email="ls@x.com", password="pw",
        )
        self.user.profile.email_verified = True
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=[
            "email_verified", "preferred_language",
        ])

    def test_placement_path_pill_renders(self):
        self.user.profile.placement_completed = True
        self.user.profile.cefr_level = "B2"
        self.user.profile.initial_cefr_level = "B1"
        self.user.profile.onboarding_path = "placement_test"
        self.user.profile.onboarding_completed = True
        self.user.profile.save(update_fields=[
            "placement_completed", "cefr_level", "initial_cefr_level",
            "onboarding_path", "onboarding_completed",
        ])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("profile"))
        self.assertContains(resp, "B2")
        self.assertContains(resp, "B1")
        self.assertContains(resp, "Took placement test")

    def test_beginner_path_pill_renders(self):
        self.user.profile.cefr_level = "A0"
        self.user.profile.initial_cefr_level = "A0"
        self.user.profile.onboarding_path = "beginner_start"
        self.user.profile.onboarding_completed = True
        self.user.profile.save(update_fields=[
            "cefr_level", "initial_cefr_level",
            "onboarding_path", "onboarding_completed",
        ])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("profile"))
        self.assertContains(resp, "A0")
        self.assertContains(resp, "Started from beginner")
