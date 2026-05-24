"""Security hardening tests for the accounts surface.

Covers:
  * Password-reset POST is rate-limited per IP.
  * Logout view is POST-only (GET-logout is a CSRF vector).
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


@override_settings(AXES_ENABLED=False, PASSWORD_RESET_RATE_LIMIT_PER_IP_PER_HOUR=3)
class PasswordResetThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        # The rate-limit module re-reads the setting at import time, so
        # we patch the module constant directly for this test class.
        from accounts import views as accounts_views
        self._orig = accounts_views.PASSWORD_RESET_RATE_LIMIT_PER_IP_PER_HOUR
        accounts_views.PASSWORD_RESET_RATE_LIMIT_PER_IP_PER_HOUR = 3

    def tearDown(self):
        from accounts import views as accounts_views
        accounts_views.PASSWORD_RESET_RATE_LIMIT_PER_IP_PER_HOUR = self._orig
        cache.clear()

    def test_password_reset_post_is_rate_limited_per_ip(self):
        url = reverse("password_reset")
        # First 3 POSTs from the same IP should succeed (302 redirect
        # to /done/ regardless of whether the email exists).
        for _ in range(3):
            r = self.client.post(url, {"email": "x@example.com"})
            self.assertEqual(r.status_code, 302)
        # 4th hits the rate limit → bounce back to the form.
        r = self.client.post(url, {"email": "x@example.com"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/auth/password-reset/", r["Location"])
        self.assertNotIn("/done/", r["Location"])


@override_settings(AXES_ENABLED=False)
class LogoutMethodTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="logme@x.com", email="logme@x.com", password="logmepw12",
        )
        self.client.force_login(self.user)

    def test_logout_get_is_rejected(self):
        """GET on /auth/logout/ must NOT log the user out — that would
        be a CSRF vulnerability via <img src="/auth/logout/">."""
        r = self.client.get(reverse("logout"))
        self.assertEqual(r.status_code, 405)
        # And the session is still active.
        self.assertIn("_auth_user_id", self.client.session)

    def test_logout_post_works(self):
        r = self.client.post(reverse("logout"))
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)
