"""Security HTTP headers — CSP + Permissions-Policy.

Django's built-in ``SecurityMiddleware`` covers HSTS / SSL redirect /
nosniff / referrer-policy, but it does NOT set:
  * Content-Security-Policy — defends against script injection.
  * Permissions-Policy — denies third-party use of mic/camera/geolocation.

We don't pull the ``django-csp`` package just to set two headers — a
~20-line middleware reads two strings from settings and stamps them
on every response. Empty / unset → no header, which keeps dev clean.
"""
from __future__ import annotations

from django.conf import settings


class SecurityHeadersMiddleware:
    """Stamp Content-Security-Policy + Permissions-Policy on responses.

    Only the values declared in settings are emitted; this lets us
    enable them in production.py without touching dev.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp_policy = (getattr(settings, "CSP_POLICY", "") or "").strip()
        self.csp_report_only = bool(getattr(settings, "CSP_REPORT_ONLY", False))
        self.permissions_policy = (
            getattr(settings, "PERMISSIONS_POLICY", "") or ""
        ).strip()
        # COOP / CORP isolate the document from cross-origin attackers
        # (Spectre-class side channels + window references). Off by
        # default — set in production.
        self.coop = (getattr(settings, "CROSS_ORIGIN_OPENER_POLICY", "") or "").strip()

    def __call__(self, request):
        response = self.get_response(request)
        if self.csp_policy:
            header = (
                "Content-Security-Policy-Report-Only"
                if self.csp_report_only
                else "Content-Security-Policy"
            )
            # Don't clobber a per-view override.
            response.setdefault(header, self.csp_policy)
        if self.permissions_policy:
            response.setdefault("Permissions-Policy", self.permissions_policy)
        if self.coop:
            response.setdefault("Cross-Origin-Opener-Policy", self.coop)
        return response
