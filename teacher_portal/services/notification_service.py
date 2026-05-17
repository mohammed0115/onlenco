from __future__ import annotations

from notifications import constants as C
from notifications.models import NotificationEvent


def create_teacher_notification(*, teacher, event_type: str, actor=None, payload=None, priority=None):
    return NotificationEvent.objects.create(
        event_type=event_type,
        user=teacher,
        actor=actor,
        payload=payload or {},
        priority=priority or C.PRIORITY_NORMAL,
        status=C.STATUS_PROCESSED,
    )

