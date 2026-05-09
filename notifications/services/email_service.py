"""EmailService — thin wrapper over Django's email backend.

The service swallows SMTP exceptions and returns a structured result
instead. Callers (notably NotificationService) record the outcome on
EmailNotification and never re-raise to user-facing views.

Sender formatting:
    Always sends as `Onlenco <addr>` so recipient mail clients show
    "Onlenco" as the friendly name regardless of the SMTP login
    (`info@…`). The brand name is overridable via
    `settings.EMAIL_BRAND_NAME` (default "Onlenco").

Brand logo (inline):
    The Onlenco logo is attached to every multipart message as an
    inline CID image (`logo@onlenco`). Templates reference it via
    `<img src="cid:logo@onlenco">` so the image renders even when the
    client refuses to load remote images.
"""
from __future__ import annotations

import logging
import mimetypes
from dataclasses import dataclass
from email.mime.image import MIMEImage
from email.utils import formataddr, parseaddr
from pathlib import Path
from typing import Iterable, Optional

from django.conf import settings
from django.core.mail import EmailMultiAlternatives

logger = logging.getLogger(__name__)


# Single Content-ID used across every Onlenco email so templates can
# unconditionally reference `<img src="cid:logo@onlenco">`.
LOGO_CID = "logo@onlenco"


def _branded_from_address(raw: str | None = None) -> str:
    """Return `Onlenco <addr>` even when `DEFAULT_FROM_EMAIL` is bare.

    If `raw` already includes a display name (e.g. `Onlenco <…>`), keep
    it. Otherwise prepend `EMAIL_BRAND_NAME` (default "Onlenco").
    """
    candidate = (raw or "").strip() or settings.DEFAULT_FROM_EMAIL or ""
    name, addr = parseaddr(candidate)
    brand = getattr(settings, "EMAIL_BRAND_NAME", "Onlenco") or "Onlenco"
    if not addr:
        # `parseaddr` failed; fall back to the raw value so SMTP can
        # still attempt delivery rather than silently dropping the mail.
        return candidate
    if not name:
        name = brand
    return formataddr((name, addr))


def _logo_path() -> Optional[Path]:
    """Resolve the static logo on disk. Looks at STATIC_ROOT first
    (post-collectstatic), then falls back to BASE_DIR/static."""
    base = Path(getattr(settings, "BASE_DIR", "."))
    candidates = [
        Path(getattr(settings, "STATIC_ROOT", "")) / "img" / "onlenco-logo.png",
        base / "static" / "img" / "onlenco-logo.png",
    ]
    for p in candidates:
        if p and p.is_file():
            return p
    return None


def _attach_inline_logo(msg: EmailMultiAlternatives) -> None:
    """Best-effort: attach the brand logo as an inline `cid:` image."""
    p = _logo_path()
    if not p:
        return
    try:
        with open(p, "rb") as fh:
            data = fh.read()
        ctype, _ = mimetypes.guess_type(str(p))
        subtype = (ctype or "image/png").split("/", 1)[1]
        img = MIMEImage(data, _subtype=subtype)
        img.add_header("Content-ID", f"<{LOGO_CID}>")
        img.add_header("Content-Disposition", "inline", filename=p.name)
        msg.attach(img)
    except Exception as e:  # pragma: no cover — never block delivery
        logger.warning("Could not attach inline logo: %s", e)


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
        reply_to: Optional[Iterable[str]] = None,
        list_unsubscribe_url: str | None = None,
    ) -> EmailResult:
        if not recipient_email:
            return EmailResult(False, "no recipient email")
        from_addr = _branded_from_address(from_email)

        # Default Reply-To pulled from settings so all emails are answerable
        # from the same human-monitored mailbox.
        reply_addrs = list(reply_to or []) if reply_to else []
        if not reply_addrs:
            default_reply = getattr(settings, "EMAIL_REPLY_TO", "") or ""
            if default_reply:
                reply_addrs = [default_reply]

        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body or _strip_html(html_body),
                from_email=from_addr,
                to=[recipient_email],
                reply_to=reply_addrs or None,
            )
            # Mixed/related parts so inline images live alongside HTML.
            msg.mixed_subtype = "related"
            msg.attach_alternative(html_body, "text/html")

            # RFC 8058 one-click unsubscribe headers — Gmail/Outlook surface
            # a "Unsubscribe" button when both are present.
            if list_unsubscribe_url:
                msg.extra_headers["List-Unsubscribe"] = f"<{list_unsubscribe_url}>"
                msg.extra_headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

            _attach_inline_logo(msg)

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
