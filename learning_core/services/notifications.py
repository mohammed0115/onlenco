"""Backwards-compatible shim.

The old `notify_weekly_assessment_ready` lived here and called `send_mail`
directly. Notifications are now centralised in the `notifications` app.
This shim proxies into `NotificationService.trigger` so any external
caller using the old name continues to work.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def notify_weekly_assessment_ready(user, assessment, *, base_url: str | None = None) -> bool:
    try:
        from notifications import constants as C
        from notifications.services import NotificationService
        NotificationService().trigger(
            C.WEEKLY_ASSESSMENT_AVAILABLE,
            user=user,
            payload={
                "cta_url": f"/dashboard/weekly/{assessment.id}/",
                "cta_label": "Open assessment",
                "dedup_key": f"weekly:{assessment.id}",
            },
        )
        return True
    except Exception as e:
        logger.warning("notify_weekly_assessment_ready shim failed: %s", e)
        return False
