"""Account service layer.

Thin orchestrators that views (and future API views) can call. Keeps
auth-related side-effects in one place so they're reusable.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


@transaction.atomic
def register_user(*, username: str, email: str, password: str, full_name: str = "") -> User:
    """Create a User. Profile is auto-created via post_save signal."""
    user = User.objects.create_user(username=username, email=email, password=password)
    if full_name and hasattr(user, "profile"):
        user.profile.full_name = full_name
        user.profile.save(update_fields=["full_name"])

    # Notifications: welcome + verification + admin alert. Best-effort, never blocks.
    try:
        from notifications import constants as C
        from notifications.services import NotificationService, issue_verification_token
        notifier = NotificationService()
        notifier.trigger(
            C.USER_REGISTERED,
            user=user,
            payload={"cta_url": "/placement/", "cta_label": "Start placement test"},
        )
        if user.email:
            issue_verification_token(user)
        notifier.notify_admins(
            C.NEW_STUDENT_REGISTERED,
            payload={
                "username": user.username,
                "email": user.email,
                "joined_at": user.date_joined.isoformat() if getattr(user, "date_joined", None) else "",
                "cta_url": "/admin/auth/user/",
                "cta_label": "Open admin",
            },
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("notify on register failed")

    return user
