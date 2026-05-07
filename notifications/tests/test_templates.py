from django.test import TestCase

from notifications.services.template_renderer import TemplateRenderer
from notifications import constants as C


class TemplateRendererTests(TestCase):
    def test_arabic_renders_rtl(self):
        r = TemplateRenderer().render(
            C.PLACEMENT_COMPLETED,
            "ar",
            {"recipient_name": "علي", "payload": {"cefr_level": "B1"}, "site_name": "Onlenco", "cta_url": "/", "cta_label": "Open"},
        )
        self.assertIn('dir="rtl"', r.html)
        self.assertIn("B1", r.html)

    def test_english_renders_ltr(self):
        r = TemplateRenderer().render(
            C.PLACEMENT_COMPLETED,
            "en",
            {"recipient_name": "Ali", "payload": {"cefr_level": "B1"}, "site_name": "Onlenco", "cta_url": "/", "cta_label": "Open"},
        )
        self.assertIn('dir="ltr"', r.html)
        self.assertIn("B1", r.html)

    def test_subject_localised(self):
        en = TemplateRenderer().render(C.PAYMENT_APPROVED, "en", {"site_name": "Onlenco", "payload": {}, "recipient_name": "x"})
        ar = TemplateRenderer().render(C.PAYMENT_APPROVED, "ar", {"site_name": "Onlenco", "payload": {}, "recipient_name": "x"})
        self.assertNotEqual(en.subject, ar.subject)

    def test_unknown_event_falls_back_to_base(self):
        # An unmapped event_type still renders without crashing.
        r = TemplateRenderer().render("totally_unknown_event", "en", {
            "recipient_name": "x", "payload": {}, "site_name": "Onlenco",
            "cta_url": "/", "cta_label": "Open",
        })
        self.assertIn("Onlenco", r.html)
