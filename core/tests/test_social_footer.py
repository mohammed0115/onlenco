"""Footer social links — env-gated, render only when configured."""
from django.test import TestCase, override_settings


class SocialFooterTests(TestCase):
    URL = "/english-for-beginners/"  # public page, renders the site footer

    def test_no_social_links_by_default(self):
        html = self.client.get(self.URL).content.decode()
        self.assertNotIn('aria-label="Facebook"', html)
        self.assertNotIn('aria-label="Instagram"', html)

    @override_settings(
        SOCIAL_FACEBOOK_URL="https://facebook.com/onlenco",
        SOCIAL_INSTAGRAM_URL="https://instagram.com/onlenco",
    )
    def test_configured_links_render(self):
        html = self.client.get(self.URL).content.decode()
        self.assertIn('href="https://facebook.com/onlenco"', html)
        self.assertIn('aria-label="Facebook"', html)
        self.assertIn('href="https://instagram.com/onlenco"', html)
        # Unconfigured ones stay hidden.
        self.assertNotIn('aria-label="YouTube"', html)

    @override_settings(SOCIAL_X_URL="https://x.com/onlenco")
    def test_only_configured_subset_renders(self):
        html = self.client.get(self.URL).content.decode()
        self.assertIn('aria-label="X"', html)
        self.assertNotIn('aria-label="Facebook"', html)
