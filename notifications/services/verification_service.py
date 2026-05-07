"""Email verification token issuance + redemption."""
from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.utils import timezone

from .. import constants as C
from ..models import EmailVerificationToken
from .notification_service import NotificationService

logger = logging.getLogger(__name__)

TOKEN_TTL = timedelta(hours=48)


def issue_verification_token(user) -> EmailVerificationToken | None:
    """Create a token + email it to the user. Returns the token (or None
    if user has no email)."""
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        return None
    token = EmailVerificationToken.objects.create(
        user=user,
        token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + TOKEN_TTL,
    )
    try:
        NotificationService().trigger(
            C.EMAIL_VERIFICATION,
            user=user,
            payload={
                "cta_url": f"/auth/verify/{token.token}/",
                "cta_label": "Verify email",
                "dedup_key": f"verify:{token.id}",
            },
        )
    except Exception as e:
        logger.warning("issue_verification_token: notify failed: %s", e)
    return token


def consume_verification_token(token_value: str) -> bool:
    """Mark the token as used; sets `Profile.email_verified=True` if the
    Profile model has that flag (added below). Returns True on success."""
    token = EmailVerificationToken.objects.filter(token=token_value).first()
    if not token or not token.is_valid():
        return False
    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])
    profile = getattr(token.user, "profile", None)
    if profile is not None and hasattr(profile, "email_verified"):
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
    return True
