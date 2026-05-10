from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    """DRF token auth with a configurable max age.

    DRF's built-in TokenAuthentication issues permanent bearer tokens.
    For mobile/API clients we keep the same simple `Token <key>` contract,
    but reject and delete tokens after `API_TOKEN_MAX_AGE_DAYS`.
    """

    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        max_age_days = int(getattr(settings, "API_TOKEN_MAX_AGE_DAYS", 30) or 0)

        if max_age_days > 0:
            expires_at = token.created + timedelta(days=max_age_days)
            if expires_at <= timezone.now():
                token.delete()
                raise AuthenticationFailed("Token has expired.")

        return user, token
