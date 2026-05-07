"""Optional Celery tasks for asynchronous notification dispatch.

These tasks are no-ops unless Celery is installed *and* a broker is
configured. The synchronous `NotificationService` keeps working without
them. To migrate to async dispatch:

  - Install celery + redis client.
  - In `NotificationService.trigger`, replace `self.process_event(event)`
    with `dispatch_event_async.delay(event.id)`.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

try:
    from celery import shared_task  # type: ignore
except ImportError:  # pragma: no cover
    shared_task = None  # noqa


def _dispatch(event_id: int) -> None:
    from .models import NotificationEvent
    from .services.notification_service import NotificationService

    event = NotificationEvent.objects.filter(pk=event_id).first()
    if event is None:
        return
    NotificationService().process_event(event)


if shared_task is not None:  # pragma: no branch
    @shared_task(name="notifications.dispatch_event_async")
    def dispatch_event_async(event_id: int) -> None:
        try:
            _dispatch(event_id)
        except Exception as e:
            logger.warning("dispatch_event_async failed for event %s: %s", event_id, e)


    @shared_task(name="notifications.retry_failed_emails")
    def retry_failed_emails() -> None:
        from .models import EmailNotification
        from .services.notification_service import NotificationService

        svc = NotificationService()
        for em in EmailNotification.objects.filter(status="failed").iterator():
            try:
                svc.retry_failed_email(em)
            except Exception as e:
                logger.warning("retry_failed_emails: %s", e)
