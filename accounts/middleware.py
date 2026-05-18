import logging

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import translation
from django.utils import timezone


logger = logging.getLogger(__name__)


# Paths that authenticated users with a forced password change can still hit
# (logout, the change page itself, language toggle, static assets, etc.)
_PASSWORD_CHANGE_ALLOWED_PREFIXES = (
    "/auth/logout/",
    "/auth/change-password/",
    "/auth/password-reset/",
    "/set-language/",
    "/static/",
    "/media/",
    "/healthz",
)


class ForcePasswordChangeMiddleware:
    """Redirect users with ``must_change_password=True`` to the change page.

    Triggered for accounts created by an admin via the teacher-registration
    flow (one-shot temporary password) — they cannot reach any other page
    until they pick a real password.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if (
            user is not None
            and getattr(user, "is_authenticated", False)
            and getattr(getattr(user, "profile", None), "must_change_password", False)
            and not any(request.path.startswith(p) for p in _PASSWORD_CHANGE_ALLOWED_PREFIXES)
        ):
            try:
                return redirect(reverse("change_password"))
            except Exception:
                pass
        return self.get_response(request)


class LanguagePreferenceMiddleware:
    """Activates the user's preferred language for each request.

    For **authenticated users** the profile is authoritative — we
    always re-apply `Profile.preferred_language` (and re-sync the
    session so subsequent middleware sees a consistent value).

    For **anonymous users** we let Django's `LocaleMiddleware` do its
    normal job: ?lang= → session → Accept-Language → settings.LANGUAGE_CODE.

    Why the older "respect session over profile" rule was wrong:
    a stale `django_language` cookie from an anonymous visit could
    override an explicit AR profile preference, leaving the user
    stuck on EN even though their profile said AR.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and hasattr(request.user, "profile")
        ):
            lang = request.user.profile.preferred_language
            if lang in {"ar", "en"}:
                translation.activate(lang)
                request.LANGUAGE_CODE = lang
                # Keep the session in sync so the next page load (and
                # any code that reads session['django_language'] directly)
                # agrees with the profile.
                if request.session.get("django_language") != lang:
                    request.session["django_language"] = lang
        return self.get_response(request)


class ExpireSubscriptionMiddleware:
    """Lazily expires subscriptions at request time for authenticated users."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if request.user.is_authenticated and hasattr(request.user, "profile"):
                profile = request.user.profile
                if (
                    profile.subscription_status == "active"
                    and profile.subscription_expires_at is not None
                    and profile.subscription_expires_at <= timezone.now()
                ):
                    profile.subscription_status = "expired"
                    profile.save(update_fields=["subscription_status"])
        except Exception as e:
            logger.warning("ExpireSubscriptionMiddleware failed: %s", e)

        return self.get_response(request)
