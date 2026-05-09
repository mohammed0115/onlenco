"""Locks the middleware contract: an authenticated user's
`Profile.preferred_language` is *always* applied, even when the session
carries a stale `django_language` value from a previous visit.

Reproduces the bug shown in the May 9 audit: a user with profile AR
saw an EN dashboard because their session still held `django_language=en`
from an anonymous browse before signup."""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import translation

User = get_user_model()


@override_settings(AXES_ENABLED=False)
class ProfileBeatsStaleSessionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ar-user@x.com", email="ar-user@x.com", password="pw",
        )
        self.user.profile.preferred_language = "ar"
        self.user.profile.email_verified = True
        self.user.profile.onboarding_completed = True   # skip onboarding redirect
        self.user.profile.save(update_fields=[
            "preferred_language", "email_verified", "onboarding_completed",
        ])

    def test_profile_ar_beats_stale_session_en(self):
        # Simulate the bug: session was set to EN during an anonymous
        # browse (e.g. user clicked the language toggle while logged out).
        session = self.client.session
        session["django_language"] = "en"
        session.save()

        self.client.force_login(self.user)
        # Hit any authenticated page; middleware re-applies profile lang.
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        # The page rendered Arabic header text proving the profile won.
        self.assertContains(resp, "مرحباً بعودتك")  # dash.welcome — AR

    def test_profile_en_beats_stale_session_ar(self):
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])

        session = self.client.session
        session["django_language"] = "ar"
        session.save()

        self.client.force_login(self.user)
        resp = self.client.get(reverse("dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Welcome back")

    def test_session_is_resynced_to_match_profile(self):
        session = self.client.session
        session["django_language"] = "en"
        session.save()

        self.client.force_login(self.user)
        self.client.get(reverse("dashboard"))
        # After the request, the session has been updated to the
        # profile's value so subsequent code agrees.
        self.assertEqual(self.client.session.get("django_language"), "ar")

    def test_anonymous_request_uses_settings_default(self):
        # Anonymous user with no session lang → Django's LocaleMiddleware
        # picks up settings.LANGUAGE_CODE (which is "ar").
        resp = self.client.get(reverse("home"))
        self.assertEqual(resp.status_code, 200)
        # The home template's HTML should be lang="ar".
        self.assertContains(resp, 'lang="ar"')