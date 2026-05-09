"""Extra tests covering markdown-mode behaviour, settings overrides, and
notification-template override safety."""
from django.test import TestCase, override_settings

from core.services.text_humanizer import (
    humanize_event_name,
    humanize_field_name,
    humanize_for_speech,
    humanize_text,
)


class MarkdownPreservedInDisplayModeTests(TestCase):
    def test_bold_kept_in_display(self):
        out = humanize_text("Try **bold** text")
        self.assertIn("**bold**", out)

    def test_inline_code_kept_in_display(self):
        out = humanize_text("Use `print()` to debug")
        self.assertIn("`print()`", out)

    def test_url_kept_in_display(self):
        out = humanize_text("See https://example.com for help")
        self.assertIn("https://example.com", out)

    def test_bold_stripped_in_speech(self):
        out = humanize_for_speech("Try **bold** text")
        self.assertNotIn("**", out)
        self.assertIn("bold", out)

    def test_code_stripped_in_speech(self):
        out = humanize_for_speech("Use `weekly_assessment` model")
        self.assertNotIn("`", out)


@override_settings(
    TEXT_HUMANIZER_EVENT_NAMES_EN={"my_custom_event": "My Custom Event Fired"},
    TEXT_HUMANIZER_EVENT_NAMES_AR={"my_custom_event": "تم إطلاق الحدث المخصص"},
    TEXT_HUMANIZER_FIELD_NAMES_EN={"custom_metric": "your custom metric"},
    TEXT_HUMANIZER_FIELD_NAMES_AR={"custom_metric": "مؤشرك المخصص"},
)
class GlossarySettingsExtensionTests(TestCase):
    def test_extra_event_used_english(self):
        self.assertEqual(
            humanize_event_name("my_custom_event"),
            "My Custom Event Fired",
        )

    def test_extra_event_used_arabic(self):
        self.assertEqual(
            humanize_event_name("my_custom_event", language="ar"),
            "تم إطلاق الحدث المخصص",
        )

    def test_extra_field_used_inline(self):
        self.assertEqual(
            humanize_text("Your custom_metric improved"),
            "Your your custom metric improved",
        )

    def test_extra_field_arabic_lookup(self):
        self.assertEqual(
            humanize_field_name("custom_metric", language="ar"),
            "مؤشرك المخصص",
        )


class NotificationOverrideSafetyTests(TestCase):
    def test_admin_subject_with_snake_case_is_humanised(self):
        from notifications.models import NotificationTemplate
        from notifications.services.template_renderer import TemplateRenderer

        NotificationTemplate.objects.create(
            event_type="payment_approved",
            language="en",
            subject="Heads up: payment_approved status",
            template_name="payment_approved.html",
            is_active=True,
        )
        rendered = TemplateRenderer().render(
            "payment_approved", "en",
            {"recipient_name": "Ali", "site_name": "Onlenco", "payload": {}, "cta_url": "/"},
        )
        # Underscore must be cleaned out of the user-facing subject.
        self.assertNotIn("payment_approved", rendered.subject)
        # The mapped phrase should be present.
        self.assertIn("Payment approved", rendered.subject)
