"""Email verification — issuance + redemption (URL token OR 6-digit OTP)."""
from __future__ import annotations

import logging
import secrets
from datetime import timedelta
from typing import Optional

from django.utils import timezone

from .. import constants as C
from ..models import EmailVerificationToken
from .notification_service import NotificationService

logger = logging.getLogger(__name__)

TOKEN_TTL = timedelta(minutes=15)


def _make_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def issue_verification_token(user) -> Optional[EmailVerificationToken]:
    """Create a fresh token, invalidate any previous unused ones, and email
    the user the OTP code. Returns the token (or None if no email)."""
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        return None

    EmailVerificationToken.objects.filter(user=user, used_at__isnull=True).update(
        used_at=timezone.now()
    )

    token = EmailVerificationToken.objects.create(
        user=user,
        token=secrets.token_urlsafe(32),
        code=_make_code(),
        expires_at=timezone.now() + TOKEN_TTL,
    )

    try:
        NotificationService().trigger(
            C.EMAIL_VERIFICATION,
            user=user,
            payload={
                "code": token.code,
                "ttl_minutes": int(TOKEN_TTL.total_seconds() // 60),
                "cta_url": f"/auth/verify-email/?code={token.code}",
                "cta_label": "Verify email",
                "dedup_key": f"verify:{token.id}",
            },
        )
    except Exception as e:
        logger.warning("issue_verification_token: notify failed: %s", e)
    return token


def consume_verification_token(value: str, *, user=None) -> bool:
    """Consume a verification token by either its URL value or its 6-digit code.

    Pass `user=` to scope the lookup (used by the OTP form so two users
    typing the same code can't accidentally redeem each other's token).
    """
    value = (value or "").strip()
    if not value:
        return False

    qs = EmailVerificationToken.objects.filter(used_at__isnull=True)
    if user is not None:
        qs = qs.filter(user=user)

    if value.isdigit() and len(value) == 6:
        token = qs.filter(code=value).order_by("-created_at").first()
    else:
        token = qs.filter(token=value).first()

    if token is None:
        return False
    if not token.is_valid():
        if value.isdigit():
            EmailVerificationToken.objects.filter(pk=token.pk).update(
                attempts=token.attempts + 1
            )
        return False

    token.used_at = timezone.now()
    token.save(update_fields=["used_at"])

    profile = getattr(token.user, "profile", None)
    if profile is not None and hasattr(profile, "email_verified"):
        profile.email_verified = True
        profile.save(update_fields=["email_verified"])
    return True
