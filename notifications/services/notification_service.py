"""NotificationService — public API for triggering and processing events."""
from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from typing import Iterable

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone

from .. import constants as C
from ..models import EmailNotification, NotificationEvent
from .email_service import EmailService
from .preference_service import PreferenceService
from .template_renderer import TemplateRenderer

logger = logging.getLogger(__name__)
User = get_user_model()

DEDUP_WINDOW = timedelta(hours=1)

# Cap how many delivery attempts we make per email. After this, status stays
# "failed" but `retry_failed_email` becomes a no-op. Operators can still
# manually re-trigger by editing the row.
MAX_ATTEMPTS = 5


def _json_safe(value):
    """Recursively drop non-JSON-serialisable values (User instances etc.)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items() if _is_jsonable(v)}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value if _is_jsonable(v)]
    return None


def _is_jsonable(v) -> bool:
    if v is None or isinstance(v, (bool, int, float, str)):
        return True
    if isinstance(v, dict):
        return all(isinstance(k, str) for k in v.keys())
    if isinstance(v, (list, tuple)):
        return True
    return False


class NotificationService:
    """Trigger events, fan out to recipients, render + send emails."""

    def __init__(
        self,
        email_service: EmailService | None = None,
        renderer: TemplateRenderer | None = None,
        preferences: PreferenceService | None = None,
    ):
        self.email = email_service or EmailService()
        self.renderer = renderer or TemplateRenderer()
        self.preferences = preferences or PreferenceService()

    # --- public API ---

    def trigger(
        self,
        event_type: str,
        *,
        user=None,
        actor=None,
        payload: dict | None = None,
        priority: str = C.PRIORITY_NORMAL,
    ) -> NotificationEvent:
        """Create the event and dispatch it synchronously. Never raises."""
        event = NotificationEvent.objects.create(
            event_type=event_type,
            user=user,
            actor=actor,
            payload=payload or {},
            priority=priority,
        )
        try:
            self.process_event(event)
        except Exception as e:
            logger.exception("NotificationService.trigger failed: %s", e)
            event.status = C.STATUS_FAILED
            event.error_message = str(e)[:500]
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_message", "processed_at"])
        return event

    def notify_admins(
        self,
        event_type: str,
        *,
        payload: dict | None = None,
        priority: str = C.PRIORITY_NORMAL,
    ) -> NotificationEvent:
        """Fan-out variant that targets every admin/staff user with email."""
        event = NotificationEvent.objects.create(
            event_type=event_type,
            user=None,
            actor=None,
            payload=payload or {},
            priority=priority,
        )
        try:
            self._dispatch_to_admins(event)
            self._mark_processed(event)
        except Exception as e:
            logger.exception("NotificationService.notify_admins failed: %s", e)
            event.status = C.STATUS_FAILED
            event.error_message = str(e)[:500]
            event.processed_at = timezone.now()
            event.save(update_fields=["status", "error_message", "processed_at"])
        return event

    def process_event(self, event: NotificationEvent) -> None:
        """Render + send for the event's user (if any) plus admin fan-out
        when the event_type lives in `ADMIN_ONLY_EVENTS`."""
        if event.event_type in C.ADMIN_ONLY_EVENTS:
            self._dispatch_to_admins(event)
        elif event.user is not None:
            self._dispatch_to_user(event, event.user)
        # else: orphan event — nothing to send, mark processed.
        self._mark_processed(event)

    def retry_failed_email(self, email_notification: EmailNotification) -> EmailNotification:
        """Re-render and resend a previously failed email.

        Honors `MAX_ATTEMPTS`: once exhausted, returns immediately without
        re-sending. The row keeps its `failed` status with the latest error.
        """
        if email_notification.status != C.STATUS_FAILED:
            return email_notification
        if email_notification.attempts_count >= MAX_ATTEMPTS:
            email_notification.error_message = (
                f"max attempts ({MAX_ATTEMPTS}) reached; not retrying"
            )[:500]
            email_notification.save(update_fields=["error_message"])
            return email_notification
        ctx = email_notification.metadata.get("context", {}) or {}
        # Best-effort re-render so subject/body reflect any template changes
        rendered = self.renderer.render(
            event_type=email_notification.event.event_type,
            language=email_notification.language,
            context=ctx,
        )
        result = self.email.send_email(
            recipient_email=email_notification.recipient_email,
            subject=rendered.subject,
            html_body=rendered.html,
        )
        email_notification.attempts_count += 1
        email_notification.last_attempt_at = timezone.now()
        if result.success:
            email_notification.status = C.STATUS_SENT
            email_notification.sent_at = timezone.now()
            email_notification.error_message = ""
        else:
            email_notification.status = C.STATUS_FAILED
            email_notification.error_message = result.error_message
        email_notification.save(update_fields=[
            "attempts_count", "last_attempt_at", "status", "sent_at", "error_message",
        ])
        return email_notification

    # --- internals ---

    def _dispatch_to_user(self, event: NotificationEvent, user) -> None:
        if not self.preferences.can_send(user, event.event_type):
            self._record_skipped(event, user, reason="pref_or_email")
            return
        if self._is_duplicate(event, user):
            self._record_skipped(event, user, reason="duplicate")
            return
        self._send_one(event, user)

    def _dispatch_to_admins(self, event: NotificationEvent) -> None:
        admins: Iterable = (
            User.objects.filter(is_staff=True, email__isnull=False)
            .exclude(email="")
            .distinct()
        )
        for admin in admins:
            if not self.preferences.can_send(admin, event.event_type):
                self._record_skipped(event, admin, reason="pref_or_email")
                continue
            if self._is_duplicate(event, admin):
                self._record_skipped(event, admin, reason="duplicate")
                continue
            self._send_one(event, admin)

    def _send_one(self, event: NotificationEvent, recipient) -> EmailNotification:
        language = self.preferences.get_language(recipient)
        recipient_name = (
            getattr(getattr(recipient, "profile", None), "full_name", "")
            or getattr(recipient, "get_username", lambda: "")()
        )
        ctx = self._base_context(event, recipient)
        rendered = self.renderer.render(event.event_type, language, ctx)
        notif = EmailNotification.objects.create(
            event=event,
            user=recipient,
            recipient_email=recipient.email,
            recipient_name=recipient_name,
            subject=rendered.subject,
            template_name=rendered.template_name,
            language=language,
            metadata={
                "dedup_key": self._dedup_key(event, recipient),
                "context": _json_safe(ctx),
            },
        )
        notif.attempts_count = 1
        notif.last_attempt_at = timezone.now()
        result = self.email.send_email(
            recipient_email=recipient.email,
            subject=rendered.subject,
            html_body=rendered.html,
            list_unsubscribe_url=ctx.get("unsubscribe_url") or None,
        )
        if result.success:
            notif.status = C.STATUS_SENT
            notif.sent_at = timezone.now()
        else:
            notif.status = C.STATUS_FAILED
            notif.error_message = result.error_message
        notif.save(update_fields=[
            "status", "sent_at", "error_message", "attempts_count", "last_attempt_at",
        ])
        return notif

    def _record_skipped(self, event: NotificationEvent, user, reason: str) -> EmailNotification:
        return EmailNotification.objects.create(
            event=event,
            user=user,
            recipient_email=getattr(user, "email", "") or "",
            recipient_name=getattr(user, "get_username", lambda: "")(),
            subject="(skipped)",
            template_name="(skipped)",
            language=self.preferences.get_language(user),
            status=C.STATUS_SKIPPED,
            attempts_count=0,
            metadata={"reason": reason},
        )

    def _mark_processed(self, event: NotificationEvent) -> None:
        event.status = C.STATUS_PROCESSED
        event.processed_at = timezone.now()
        event.save(update_fields=["status", "processed_at"])

    def _is_duplicate(self, event: NotificationEvent, user) -> bool:
        key = self._dedup_key(event, user)
        cutoff = timezone.now() - DEDUP_WINDOW
        return EmailNotification.objects.filter(
            user=user,
            status__in=[C.STATUS_SENT, C.STATUS_PENDING],
            event__event_type=event.event_type,
            metadata__dedup_key=key,
            created_at__gte=cutoff,
        ).exists()

    def _dedup_key(self, event: NotificationEvent, user) -> str:
        # Stable key: event type + user id + caller-supplied dedup_key (if any)
        # If no dedup_key in payload, dedup window prevents same-event spam.
        explicit = (event.payload or {}).get("dedup_key")
        if explicit:
            return f"{event.event_type}:{user.id}:{explicit}"
        return f"{event.event_type}:{user.id}"

    def _base_context(self, event: NotificationEvent, recipient) -> dict:
        base_url = (getattr(settings, "ONLENCO_BASE_URL", "") or "").rstrip("/")
        recipient_name = (
            getattr(getattr(recipient, "profile", None), "full_name", "")
            or getattr(recipient, "get_username", lambda: "")()
        )
        cta_url = (event.payload or {}).get("cta_url") or "/"
        if base_url and cta_url.startswith("/"):
            cta_url = f"{base_url}{cta_url}"

        unsubscribe_url = ""
        try:
            from ..views import make_unsubscribe_token
            tok = make_unsubscribe_token(recipient)
            unsubscribe_url = f"/notifications/unsubscribe/{tok}/"
            if base_url:
                unsubscribe_url = f"{base_url}{unsubscribe_url}"
        except Exception:
            pass

        # Logo: every email attaches the brand logo as a CID inline image
        # (`cid:logo@onlenco`). Templates also receive a public-URL
        # fallback so providers that strip CID can still load the asset
        # over HTTPS.
        logo_public_url = ""
        if base_url:
            logo_public_url = f"{base_url}/static/img/onlenco-logo.png"

        return {
            "recipient": recipient,
            "recipient_name": recipient_name,
            "event_type": event.event_type,
            "payload": event.payload or {},
            "site_name": "Onlenco",
            "base_url": base_url,
            "cta_url": cta_url,
            "cta_label": (event.payload or {}).get("cta_label", "Open Onlenco"),
            "unsubscribe_url": unsubscribe_url,
            "logo_cid": "logo@onlenco",
            "logo_public_url": logo_public_url,
        }
