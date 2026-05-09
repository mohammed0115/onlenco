"""Account service layer.

Thin orchestrators that views (and future API views) can call. Keeps
auth-related side-effects in one place so they're reusable.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


@transaction.atomic
def register_user(
    *,
    username: str,
    email: str,
    password: str,
    full_name: str = "",
    language: str | None = None,
) -> User:
    """Create a User. Profile is auto-created via post_save signal.

    `language` should be the active request language (or any explicit
    user preference) so we can persist it onto the profile + notification
    preference at signup. Falls back to the project-wide Arabic default
    if not supplied.
    """
    user = User.objects.create_user(username=username, email=email, password=password)

    lang = (language or "").strip().lower()
    if lang.startswith("ar"):
        lang = "ar"
    elif lang.startswith("en"):
        lang = "en"
    else:
        lang = "ar"

    if hasattr(user, "profile"):
        update_fields = []
        if full_name:
            user.profile.full_name = full_name
            update_fields.append("full_name")
        if user.profile.preferred_language != lang:
            user.profile.preferred_language = lang
            update_fields.append("preferred_language")
        if update_fields:
            user.profile.save(update_fields=update_fields)

    # Mirror the language onto the user's notification preference so
    # transactional emails go out in the right language from message #1.
    try:
        from notifications.models import NotificationPreference
        pref, _ = NotificationPreference.objects.get_or_create(user=user)
        if pref.language != lang:
            pref.language = lang
            pref.save(update_fields=["language"])
    except Exception:
        import logging
        logging.getLogger(__name__).exception("notify pref language sync failed")

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
