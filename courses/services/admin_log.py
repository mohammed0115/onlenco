"""Single canonical writer for AdminActionLog rows.

Admin classes call `log_admin_action(...)` instead of touching the
model directly so the audit-trail format stays consistent.
"""
from __future__ import annotations

from ..models import AdminActionLog


def log_admin_action(
    *,
    admin_user,
    action_type: str,
    description: str = "",
    target_user=None,
    metadata: dict | None = None,
) -> AdminActionLog:
    return AdminActionLog.objects.create(
        admin_user=admin_user if getattr(admin_user, "is_authenticated", True) else None,
        target_user=target_user,
        action_type=action_type[:40],
        description=description,
        metadata=metadata or {},
    )
