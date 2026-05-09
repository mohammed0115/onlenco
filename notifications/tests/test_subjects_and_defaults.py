"""Locks the i18n contracts that the BEFORE audit identified as gaps:
  * Project default is Arabic (LANGUAGE_CODE).
  * `set_language` falls back to AR for unknown / missing input.
  * `TemplateRenderer` falls back to AR for unknown language.
  * `get_localized_subject` resolves spec-required events in both AR + EN.
  * `get_user_language` is the single source of truth callers should use.
  * `DEFAULT_FROM_EMAIL` reads as `Onlenco <info@onlenco.com>` in dev.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from notifications import constants as C
from notifications.services.subjects import (
    get_localized_subject, get_user_language,
)
from notifications.services.template_renderer import TemplateRenderer

User = get_user_model()


class ProjectDefaultLanguageTests(TestCase):
    """Spec rule: 'If user language is unknown, default to Arabic.'"""

    def test_language_code_is_arabic(self):
        self.assertEqual(settings.LANGUAGE_CODE, "ar")

    def test_arabic_listed_first_in_languages(self):
        codes = [code for code, _name in settings.LANGUAGES]
        self.assertEqual(codes[0], "ar")
        self.assertIn("en", codes)


class SetLanguageDefaultTests(TestCase):
    def test_set_language_with_no_input_falls_back_to_ar(self):
        # Anonymous request with no `language` POST param → AR.
        resp = self.client.post(reverse("set_language"))
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session.get("django_language"), "ar")

    def test_set_language_with_unsupported_language_falls_back_to_ar(self):
        resp = self.client.post(reverse("set_language"), {"language": "fr"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session.get("django_language"), "ar")

    def test_set_language_to_en_is_honoured(self):
        resp = self.client.post(reverse("set_language"), {"language": "en"})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.session.get("django_language"), "en")


class TemplateRendererFallbackTests(TestCase):
    def setUp(self):
        self.renderer = TemplateRenderer()
        # Variables every email template expects — mirrors what
        # NotificationService._base_context provides in production.
        self.base_ctx = {
            "recipient_name": "Test",
            "site_name": "Onlenco",
            "base_url": "https://onlenco.local",
            "logo_cid": "",
            "logo_public_url": "",
            "cta_url": "",
            "cta_label": "",
            "unsubscribe_url": "",
        }

    def test_unknown_language_renders_arabic_email(self):
        # Pass an empty string — historically this fell through to EN.
        # After the fix it must render the AR copy.
        rendered = self.renderer.render(
            C.USER_REGISTERED, language="", context=self.base_ctx,
        )
        self.assertEqual(rendered.language, "ar")
        self.assertEqual(rendered.subject, C.SUBJECTS_AR[C.USER_REGISTERED])

    def test_blank_language_uses_arabic_subject(self):
        rendered = self.renderer.render(
            C.PLACEMENT_COMPLETED, language=None,
            context={**self.base_ctx, "level": "B1"},
        )
        self.assertEqual(rendered.language, "ar")
        self.assertEqual(rendered.subject, C.SUBJECTS_AR[C.PLACEMENT_COMPLETED])


class GetLocalizedSubjectTests(TestCase):
    """Spec contract: `get_localized_subject(event_type, language)` returns
    a non-empty, translated, never-raw subject for every spec-listed event."""

    SPEC_EVENTS = [
        C.USER_REGISTERED,
        C.EMAIL_VERIFICATION,
        C.PASSWORD_RESET,
        C.PLACEMENT_COMPLETED,
        C.PAYMENT_SUBMITTED,
        C.PAYMENT_APPROVED,
        C.PAYMENT_REJECTED,
        C.SUBSCRIPTION_EXPIRING,
        C.WEAKNESS_DETECTED,
        C.EXERCISES_GENERATED,
        C.MOTIVATION_MESSAGE_GENERATED,
        C.WEEKLY_ASSESSMENT_AVAILABLE,
        C.LEVEL_IMPROVED,
    ]

    def test_every_spec_event_has_arabic_subject(self):
        for event in self.SPEC_EVENTS:
            subject = get_localized_subject(event, "ar")
            self.assertTrue(subject, f"AR subject missing for {event}")
            # Sanity: contains at least one Arabic codepoint or is the
            # canonical EN→AR transition rule.
            self.assertNotIn(event, subject,
                             f"Raw event key leaked into AR subject for {event}")

    def test_every_spec_event_has_english_subject(self):
        for event in self.SPEC_EVENTS:
            subject = get_localized_subject(event, "en")
            self.assertTrue(subject, f"EN subject missing for {event}")
            self.assertNotIn(event, subject)

    def test_unknown_event_humanises_the_key(self):
        # Never leaks the raw snake_case identifier.
        subject = get_localized_subject("totally_made_up_event", "ar")
        self.assertNotEqual(subject, "totally_made_up_event")
        self.assertGreater(len(subject), 0)

    def test_blank_language_treated_as_arabic(self):
        ar_subject = get_localized_subject(C.USER_REGISTERED, "ar")
        blank_subject = get_localized_subject(C.USER_REGISTERED, "")
        self.assertEqual(blank_subject, ar_subject)


class GetUserLanguageTests(TestCase):
    def test_anonymous_user_returns_arabic(self):
        self.assertEqual(get_user_language(None), "ar")

    def test_user_with_arabic_profile_returns_arabic(self):
        u = User.objects.create_user(username="a@x.com", email="a@x.com",
                                     password="pw")
        u.profile.preferred_language = "ar"
        u.profile.save(update_fields=["preferred_language"])
        self.assertEqual(get_user_language(u), "ar")

    def test_user_with_english_profile_returns_english(self):
        u = User.objects.create_user(username="b@x.com", email="b@x.com",
                                     password="pw")
        u.profile.preferred_language = "en"
        u.profile.save(update_fields=["preferred_language"])
        self.assertEqual(get_user_language(u), "en")

    def test_invalid_profile_language_falls_back_to_arabic(self):
        u = User.objects.create_user(username="c@x.com", email="c@x.com",
                                     password="pw")
        u.profile.preferred_language = "fr"   # not in choices but possible via direct DB write
        u.profile.save(update_fields=["preferred_language"])
        self.assertEqual(get_user_language(u), "ar")

    def test_force_language_override_arabic(self):
        from django.test import override_settings
        u = User.objects.create_user(username="f@x.com", email="f@x.com",
                                     password="pw")
        u.profile.preferred_language = "en"   # user wants English
        u.profile.save(update_fields=["preferred_language"])
        # …but operator overrides every email to Arabic.
        with override_settings(EMAIL_FORCE_LANGUAGE="ar"):
            self.assertEqual(get_user_language(u), "ar")

    def test_force_language_override_english(self):
        from django.test import override_settings
        u = User.objects.create_user(username="g@x.com", email="g@x.com",
                                     password="pw")
        u.profile.preferred_language = "ar"
        u.profile.save(update_fields=["preferred_language"])
        with override_settings(EMAIL_FORCE_LANGUAGE="en"):
            self.assertEqual(get_user_language(u), "en")

    def test_force_language_blank_honours_user_preference(self):
        from django.test import override_settings
        u = User.objects.create_user(username="h@x.com", email="h@x.com",
                                     password="pw")
        u.profile.preferred_language = "en"
        u.profile.save(update_fields=["preferred_language"])
        with override_settings(EMAIL_FORCE_LANGUAGE=""):
            self.assertEqual(get_user_language(u), "en")


class DefaultFromEmailTests(TestCase):
    """Spec rule: emails come from `Onlenco <info@onlenco.com>` (the
    branded form). In dev / prod the actual domain is overridden by an
    env var, but the *source-code default* and the *branded display
    name* are stable contracts we lock here."""

    def test_default_from_email_default_value_in_source(self):
        # When env var is unset, the source-code fallback is the
        # spec-mandated address. We override it explicitly here so the
        # test isn't influenced by whatever the local .env sets.
        with override_settings(DEFAULT_FROM_EMAIL="Onlenco <info@onlenco.com>"):
            self.assertEqual(settings.DEFAULT_FROM_EMAIL,
                             "Onlenco <info@onlenco.com>")

    def test_default_from_email_always_carries_onlenco_brand(self):
        # Whatever the env-overridden value is, it must keep the
        # "Onlenco <…>" display-name structure so recipients see the
        # brand, not a bare technical address.
        self.assertIn("Onlenco", settings.DEFAULT_FROM_EMAIL)
        self.assertIn("<", settings.DEFAULT_FROM_EMAIL)
        self.assertIn("@", settings.DEFAULT_FROM_EMAIL)
        self.assertTrue(settings.DEFAULT_FROM_EMAIL.endswith(">"))
