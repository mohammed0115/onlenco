"""Integration: notification subject falls back to the humanizer."""
from django.test import TestCase

from notifications.services.template_renderer import TemplateRenderer


class NotificationSubjectFallbackTests(TestCase):
    def test_unknown_event_subject_humanised_english(self):
        # `brand_new_event` is intentionally NOT in DEFAULT_SUBJECTS.
        rendered = TemplateRenderer().render(
            event_type="brand_new_event",
            language="en",
            context={"recipient_name": "Ali", "cta_url": "/x/", "site_name": "Onlenco", "payload": {}},
        )
        # It must not be the raw key.
        self.assertNotIn("_", rendered.subject)
        self.assertEqual(rendered.subject.lower(), "brand new event".lower())

    def test_unknown_event_subject_humanised_arabic(self):
        rendered = TemplateRenderer().render(
            event_type="some_unmapped_thing",
            language="ar",
            context={"recipient_name": "Ali", "cta_url": "/x/", "site_name": "Onlenco", "payload": {}},
        )
        self.assertNotIn("_", rendered.subject)

    def test_known_event_subject_unchanged(self):
        rendered = TemplateRenderer().render(
            event_type="payment_approved",
            language="en",
            context={"recipient_name": "Ali", "cta_url": "/x/", "site_name": "Onlenco", "payload": {}},
        )
        self.assertEqual(rendered.subject, "Your Onlenco subscription is active")
