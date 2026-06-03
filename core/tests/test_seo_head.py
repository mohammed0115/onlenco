"""SEO head signals: Search Console verification + GA4 are env-gated.

These guard the two genuine gaps an external SEO audit flagged — the rest of
the head (canonical, hreflang, OpenGraph, JSON-LD, clean sitemap) already
exists and is covered elsewhere. Both tokens render *only* when configured.
"""
from django.test import TestCase, override_settings


class SeoHeadTests(TestCase):
    URL = "/english-for-beginners/"  # public SEO landing, renders base.html

    def test_no_verification_or_analytics_by_default(self):
        html = self.client.get(self.URL).content.decode()
        self.assertNotIn("google-site-verification", html)
        self.assertNotIn("googletagmanager.com/gtag", html)

    @override_settings(GOOGLE_SITE_VERIFICATION="abc123token")
    def test_verification_tag_renders_when_set(self):
        html = self.client.get(self.URL).content.decode()
        self.assertIn('<meta name="google-site-verification" content="abc123token">', html)

    @override_settings(GOOGLE_ANALYTICS_ID="G-TEST12345")
    def test_ga4_snippet_renders_when_set(self):
        html = self.client.get(self.URL).content.decode()
        self.assertIn("googletagmanager.com/gtag/js?id=G-TEST12345", html)
        self.assertIn("gtag('config','G-TEST12345')", html)

    @override_settings(GOOGLE_ANALYTICS_ID="G-TEST12345")
    def test_ga4_not_loaded_on_admin_console(self):
        # Staff consoles must not ship analytics to logged-in operators.
        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.create_superuser("seo_admin", "seo@x.com", "pw12345!")
        self.client.force_login(admin)
        html = self.client.get("/admin/").content.decode()
        self.assertNotIn("googletagmanager.com/gtag", html)

    def test_canonical_and_hreflang_present(self):
        # Regression guard: the existing (audit-disputed) head signals stay.
        html = self.client.get(self.URL).content.decode()
        self.assertIn('rel="canonical"', html)
        self.assertIn('hreflang="ar"', html)
        self.assertIn('hreflang="x-default"', html)
        self.assertIn('application/ld+json', html)
