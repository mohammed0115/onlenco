from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.response import Response


class ObtainExpiringAuthToken(ObtainAuthToken):
    """Issue a fresh token when the user's existing token is stale."""

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]

        max_age_days = int(getattr(settings, "API_TOKEN_MAX_AGE_DAYS", 30) or 0)
        token = Token.objects.filter(user=user).first()
        if token and max_age_days > 0:
            expires_at = token.created + timedelta(days=max_age_days)
            if expires_at <= timezone.now():
                token.delete()
                token = None

        if token is None:
            token = Token.objects.create(user=user)

        return Response({"token": token.key})
