"""Tests for the email branded-sender + Arabic-by-default fixes."""
from email.utils import parseaddr

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from notifications import constants as C
from notifications.models import NotificationPreference
from notifications.services.email_service import EmailService, _branded_from_address
from notifications.services.notification_service import NotificationService
from notifications.services.preference_service import PreferenceService

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="info@sudaschool.academy",  # bare address
    EMAIL_BRAND_NAME="Onlenco",
    AXES_ENABLED=False,
)
class BrandedSenderTests(TestCase):
    def test_branded_helper_wraps_bare_address(self):
        out = _branded_from_address(None)
        name, addr = parseaddr(out)
        self.assertEqual(name, "Onlenco")
        self.assertEqual(addr, "info@sudaschool.academy")

    def test_branded_helper_keeps_existing_display_name(self):
        out = _branded_from_address("Custom <hello@example.com>")
        name, addr = parseaddr(out)
        self.assertEqual(name, "Custom")
        self.assertEqual(addr, "hello@example.com")

    def test_send_uses_branded_sender(self):
        EmailService().send_email(
            recipient_email="alice@example.com",
            subject="hi",
            html_body="<p>hello</p>",
        )
        self.assertEqual(len(mail.outbox), 1)
        sender_name, sender_addr = parseaddr(mail.outbox[0].from_email)
        self.assertEqual(sender_name, "Onlenco")
        self.assertNotEqual(sender_name, "info")  # the actual symptom we fixed
        self.assertEqual(sender_addr, "info@sudaschool.academy")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Onlenco <info@sudaschool.academy>",
    EMAIL_BRAND_NAME="Onlenco",
    AXES_ENABLED=False,
)
class ArabicByDefaultTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ar-default@x.com",
            email="ar-default@x.com",
            password="pw",
        )

    def test_new_user_profile_defaults_to_arabic(self):
        self.assertEqual(self.user.profile.preferred_language, "ar")

    def test_new_notification_pref_defaults_to_arabic(self):
        pref = PreferenceService().get_or_create_for(self.user)
        self.assertEqual(pref.language, "ar")

    def test_get_language_returns_ar_when_no_pref(self):
        # Wipe any pref; PreferenceService should still default to "ar".
        NotificationPreference.objects.filter(user=self.user).delete()
        # Also temporarily clear the profile language to mimic a degraded
        # state (defensive code path).
        self.user.profile.preferred_language = ""
        self.user.profile.save(update_fields=["preferred_language"])
        # Re-resolve should default to Arabic.
        self.assertEqual(PreferenceService().get_language(self.user), "ar")

    def test_arabic_user_receives_arabic_subject(self):
        # User defaults to AR. Trigger a known event.
        NotificationService().trigger(
            C.PAYMENT_APPROVED,
            user=self.user,
            payload={"site_name": "Onlenco", "cta_url": "/", "cta_label": "Open"},
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "تم قبول الدفع وتفعيل اشتراكك")
        self.assertIn("rtl", mail.outbox[0].alternatives[0][0])

    def test_english_user_receives_english_subject(self):
        # Flip preference back to English explicitly.
        self.user.profile.preferred_language = "en"
        self.user.profile.save(update_fields=["preferred_language"])
        pref = PreferenceService().get_or_create_for(self.user)
        pref.language = "en"
        pref.save(update_fields=["language"])

        NotificationService().trigger(
            C.PAYMENT_APPROVED,
            user=self.user,
            payload={"site_name": "Onlenco", "cta_url": "/", "cta_label": "Open"},
        )
        self.assertEqual(mail.outbox[-1].subject, "Your Onlenco subscription is active")


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Onlenco <info@sudaschool.academy>",
    AXES_ENABLED=False,
)
class SignupLanguageSniffTests(TestCase):
    def _post_signup(self, *, lang_header: str | None = None):
        url = reverse("auth")
        headers = {}
        if lang_header:
            headers["HTTP_ACCEPT_LANGUAGE"] = lang_header
        return self.client.post(
            url,
            {
                "mode": "signup",
                "full_name": "Test User",
                "email": f"sniff-{lang_header or 'noheader'}@example.com",
                "password": "Onlenco12345!",
            },
            **headers,
        )

    def test_arabic_browser_persists_arabic_preference(self):
        # Browser advertises Arabic; LocaleMiddleware sets request.LANGUAGE_CODE.
        self._post_signup(lang_header="ar")
        u = User.objects.get(email__startswith="sniff-ar")
        self.assertEqual(u.profile.preferred_language, "ar")
        self.assertEqual(
            NotificationPreference.objects.get(user=u).language, "ar"
        )

    def test_english_browser_persists_english_preference(self):
        self._post_signup(lang_header="en")
        u = User.objects.get(email__startswith="sniff-en")
        self.assertEqual(u.profile.preferred_language, "en")
        self.assertEqual(
            NotificationPreference.objects.get(user=u).language, "en"
        )
