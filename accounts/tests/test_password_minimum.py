"""The MVP raised the signup password minimum from 6 to 8.

These tests pin both layers — the form's ``min_length`` AND Django's
``MinimumLengthValidator`` — so a future regression to 6 would fail
loudly.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth.password_validation import MinimumLengthValidator
from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.forms import SignUpForm


class PasswordMinimumTests(TestCase):
    def _signup_payload(self, password: str) -> dict:
        return {
            "mode": "signup",
            "full_name": "Test User",
            "email": "fresh@example.com",
            "password": password,
        }

    def test_signup_form_rejects_seven_char_password(self):
        form = SignUpForm(self._signup_payload("seven12"))  # 7 chars
        self.assertFalse(form.is_valid())
        self.assertIn("password", form.errors)

    def test_signup_form_accepts_eight_char_password(self):
        form = SignUpForm(self._signup_payload("eightch1"))  # 8 chars
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_settings_minimum_length_validator_is_eight(self):
        configured = next(
            (
                v for v in settings.AUTH_PASSWORD_VALIDATORS
                if v["NAME"].endswith("MinimumLengthValidator")
            ),
            None,
        )
        self.assertIsNotNone(configured, "MinimumLengthValidator missing")
        self.assertEqual(configured["OPTIONS"]["min_length"], 8)

    def test_django_validator_rejects_seven_char_password(self):
        with self.assertRaises(ValidationError):
            MinimumLengthValidator(min_length=8).validate("seven12")
