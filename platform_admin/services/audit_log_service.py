from __future__ import annotations

from typing import Any

from platform_admin.models import PlatformAuditLog


def _strip_port(addr: str) -> str:
    # Caddy/proxies sometimes hand us "1.2.3.4:54321" or "[::1]:54321".
    # Postgres `inet` rejects those, so peel the port before storing.
    addr = addr.strip()
    if addr.startswith("[") and "]" in addr:
        return addr[1:addr.index("]")]
    if addr.count(":") == 1:
        return addr.split(":", 1)[0]
    return addr


def get_client_ip(request) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        return _strip_port(first) or None if first else None
    remote = request.META.get("REMOTE_ADDR")
    return _strip_port(remote) or None if remote else None


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
