from __future__ import annotations

from typing import Any

from platform_admin.models import PlatformAuditLog


def get_client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def log_action(
    request,
    *,
    action_type: str,
    description: str = "",
    target_user=None,
    object_type: str = "",
    object_id: Any = "",
    metadata: dict | None = None,
) -> PlatformAuditLog:
    user = getattr(request, "user", None)
    actor = user if getattr(user, "is_authenticated", False) else None
    return PlatformAuditLog.objects.create(
        actor=actor,
        target_user=target_user,
        action_type=action_type[:80],
        object_type=(object_type or "")[:80],
        object_id=str(object_id or "")[:80],
        description=description,
        metadata=metadata or {},
        ip_address=get_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:2000],
    )
