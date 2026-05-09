"""PreferenceService — decides whether a user can receive an event by email."""
from __future__ import annotations

from django.conf import settings

from .. import constants as C
from ..models import NotificationPreference


class PreferenceService:
    @staticmethod
    def get_or_create_for(user) -> NotificationPreference:
        # Language priority: explicit profile preference → site default ("ar").
        # Any future addition (request locale, IP geolocation) plugs in here.
        defaults = {
            "language": getattr(getattr(user, "profile", None), "preferred_language", "ar")
            or "ar",
        }
        pref, _ = NotificationPreference.objects.get_or_create(user=user, defaults=defaults)
        return pref

    def can_send(self, user, event_type: str) -> bool:
        """Return True if `user` should receive `event_type` by email."""
        if user is None or not getattr(user, "is_authenticated", True):
            return False
        if not (getattr(user, "email", "") or "").strip():
            return False

        # Transactional emails always go (security-critical, billing receipts).
        if event_type in C.TRANSACTIONAL_EVENTS:
            return True

        # Marketing requires explicit opt-in.
        if event_type in C.MARKETING_EVENTS:
            pref = self.get_or_create_for(user)
            return bool(pref.marketing_emails)

        pref = self.get_or_create_for(user)

        # Admin-only events also need the recipient to actually be an admin.
        if event_type in C.ADMIN_ONLY_EVENTS:
            profile = getattr(user, "profile", None)
            is_admin = (
                getattr(user, "is_staff", False)
                or getattr(user, "is_superuser", False)
                or (profile and getattr(profile, "is_admin", False))
            )
            return bool(is_admin and pref.admin_alerts)

        if event_type in C.LEARNING_EVENTS:
            return bool(pref.learning_updates)
        if event_type in C.PAYMENT_EVENTS:
            return bool(pref.payment_updates)
        if event_type in C.WEEKLY_SUMMARY_EVENTS:
            return bool(pref.weekly_summary)

        # Unknown event types default to allowed (safe default for new categories).
        return True

    def get_language(self, user) -> str:
        # Final fallback is Arabic — the project default — when no profile
        # / preference data is available.
        #
        # `EMAIL_FORCE_LANGUAGE` is the operator override: set to "ar" or
        # "en" in .env to send every email in that language regardless of
        # per-user preference. Useful when the platform is single-locale
        # and the user-preference field hasn't been backfilled.
        forced = (getattr(settings, "EMAIL_FORCE_LANGUAGE", "") or "").strip().lower()
        if forced in ("ar", "en"):
            return forced
        if user is None:
            return "ar"
        try:
            return self.get_or_create_for(user).language or "ar"
        except Exception:
            return "ar"
