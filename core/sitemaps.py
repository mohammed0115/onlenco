"""XML sitemap for the public, crawlable pages of Onlenco Academy.

Only pages that return ``200`` to an anonymous visitor belong here — the
home page and the public SEO landing pages. Everything else on the site
is behind a login wall and is intentionally excluded.
"""
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class _CanonicalSite:
    """Minimal stand-in for a ``Site`` object.

    The sitemap framework only reads ``.domain`` off the site, so this
    lets us pin every ``<loc>`` to the canonical public domain
    (``SITE_URL``) regardless of the host the request arrived on.
    """

    def __init__(self, domain: str):
        self.domain = domain


class StaticViewSitemap(Sitemap):
    """Lists the fixed public URLs by their URL name."""

    protocol = "https"

    # (url_name, priority, changefreq)
    _PAGES = [
        ("home", 1.0, "daily"),
        ("seo_pricing", 0.9, "weekly"),
        ("seo_placement_test", 0.8, "monthly"),
        ("seo_ai_english_tutor", 0.8, "monthly"),
        ("seo_english_for_beginners", 0.8, "monthly"),
        ("seo_english_speaking_practice", 0.8, "monthly"),
    ]

    def items(self):
        return self._PAGES

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):
        return item[1]

    def changefreq(self, item):
        return item[2]

    def get_urls(self, page=1, site=None, protocol=None):
        # Always emit absolute URLs on the canonical public domain.
        domain = urlsplit(getattr(settings, "SITE_URL", "")).netloc or "onlenco.academy"
        return super().get_urls(page=page, site=_CanonicalSite(domain), protocol="https")
