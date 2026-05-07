import logging

from django.utils import translation
from django.utils import timezone


logger = logging.getLogger(__name__)


class LanguagePreferenceMiddleware:
    """Activates the user's preferred language for each request.

    Priority order (highest first):
      1. ?lang= querystring (handled by /set-language/ view, which writes
         a session value)
      2. Session value `django_language` (set by the toggle button)
      3. Authenticated user's Profile.preferred_language
      4. Browser Accept-Language header (handled by LocaleMiddleware)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only step 3 is our responsibility; LocaleMiddleware handles 1, 2, 4.
        if (
            request.user.is_authenticated
            and "django_language" not in request.session
            and hasattr(request.user, "profile")
        ):
            lang = request.user.profile.preferred_language
            if lang:
                translation.activate(lang)
                request.LANGUAGE_CODE = lang
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
