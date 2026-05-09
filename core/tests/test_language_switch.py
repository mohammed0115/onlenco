from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.context_processors import site_context

User = get_user_model()


class LanguageSwitchTests(TestCase):
    def test_set_language_arabic_persists_for_user(self):
        u = User.objects.create_user(username="amal", password="pw")
        self.client.force_login(u)
        r = self.client.post(reverse("set_language"), data={"language": "ar", "next": "/"})
        self.assertEqual(r.status_code, 302)
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.preferred_language, "ar")

    def test_set_language_unknown_falls_back_to_arabic(self):
        # Project default is Arabic — `set_language` falls back to "ar"
        # for unsupported languages (was "en" before the i18n audit).
        # Spec: "If user language is unknown, default to Arabic."
        u = User.objects.create_user(username="bobby", password="pw")
        self.client.force_login(u)
        r = self.client.post(reverse("set_language"), data={"language": "fr", "next": "/"})
        self.assertEqual(r.status_code, 302)
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.preferred_language, "ar")

    def test_dir_flips_for_arabic(self):
        from django.utils import translation

        translation.activate("ar")
        ctx = site_context(request=None)
        self.assertEqual(ctx["dir"], "rtl")
        self.assertEqual(ctx["lang"], "ar")

        translation.activate("en")
        ctx = site_context(request=None)
        self.assertEqual(ctx["dir"], "ltr")
        self.assertEqual(ctx["lang"], "en")
