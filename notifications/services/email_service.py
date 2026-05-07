"""EmailService — thin wrapper over Django's email backend.

The service swallows SMTP exceptions and returns a structured result
instead. Callers (notably NotificationService) record the outcome on
EmailNotification and never re-raise to user-facing views.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    success: bool
    error_message: str = ""

    def __bool__(self) -> bool:
        return self.success


class EmailService:
    """Send a multi-part (text + html) email through Django's backend."""

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
        from_email: str | None = None,
    ) -> EmailResult:
        if not recipient_email:
            return EmailResult(False, "no recipient email")
        from_addr = from_email or settings.DEFAULT_FROM_EMAIL
        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body or _strip_html(html_body),
                from_email=from_addr,
                to=[recipient_email],
            )
            msg.attach_alternative(html_body, "text/html")
            sent = msg.send(fail_silently=False)
            if not sent:
                return EmailResult(False, "backend reported 0 delivered")
            return EmailResult(True, "")
        except Exception as e:
            logger.warning("EmailService send failed to %s: %s", recipient_email, e)
            return EmailResult(False, str(e)[:500])


def _strip_html(html: str) -> str:
    """Best-effort plain-text fallback that preserves anchor URLs."""
    import re
    text = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    text = re.sub(
        r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        r"\2 (\1)",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
