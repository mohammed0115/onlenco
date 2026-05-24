"""Pin the security-header contract.

These tests run under *test* settings (no CSP/Permissions-Policy by
default) so they verify the middleware itself, not the production
config. The production policy is exercised by overriding settings.
"""
from __future__ import annotations

from django.test import RequestFactory, TestCase, override_settings

from core.security_headers import SecurityHeadersMiddleware


def _noop_get_response(request):
    from django.http import HttpResponse
    return HttpResponse("ok")


def _build(request):
    mw = SecurityHeadersMiddleware(_noop_get_response)
    return mw(request)


class SecurityHeadersMiddlewareTests(TestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_no_csp_set_when_setting_is_empty(self):
        r = _build(self.rf.get("/"))
        self.assertNotIn("Content-Security-Policy", r.headers)
        self.assertNotIn("Content-Security-Policy-Report-Only", r.headers)

    @override_settings(CSP_POLICY="default-src 'self'")
    def test_csp_header_is_set_when_policy_configured(self):
        r = _build(self.rf.get("/"))
        self.assertEqual(r.headers.get("Content-Security-Policy"), "default-src 'self'")

    @override_settings(CSP_POLICY="default-src 'self'", CSP_REPORT_ONLY=True)
    def test_csp_report_only_when_flag_set(self):
        r = _build(self.rf.get("/"))
        self.assertNotIn("Content-Security-Policy", r.headers)
        self.assertEqual(
            r.headers.get("Content-Security-Policy-Report-Only"),
            "default-src 'self'",
        )

    @override_settings(PERMISSIONS_POLICY="camera=(self), microphone=(self)")
    def test_permissions_policy_header_is_set(self):
        r = _build(self.rf.get("/"))
        self.assertEqual(
            r.headers.get("Permissions-Policy"),
            "camera=(self), microphone=(self)",
        )

    @override_settings(CROSS_ORIGIN_OPENER_POLICY="same-origin")
    def test_coop_header_is_set(self):
        r = _build(self.rf.get("/"))
        self.assertEqual(r.headers.get("Cross-Origin-Opener-Policy"), "same-origin")

    @override_settings(CSP_POLICY="default-src 'self'")
    def test_does_not_overwrite_existing_csp(self):
        from django.http import HttpResponse

        def app(request):
            resp = HttpResponse("ok")
            resp["Content-Security-Policy"] = "default-src https://example.com"
            return resp

        mw = SecurityHeadersMiddleware(app)
        r = mw(self.rf.get("/"))
        self.assertEqual(
            r.headers.get("Content-Security-Policy"),
            "default-src https://example.com",
        )
