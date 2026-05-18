"""Email SMTP end-to-end diagnostic.

Usage:
    python manage.py email_smtp_check
    python manage.py email_smtp_check --to admin@example.com

Output:
    - resolved settings (backend, host, port, TLS, from)
    - SMTP greeting + auth check
    - actual test message via EmailService (the same code path signup uses)
    - last 5 EmailNotification rows for context

Designed for support staff to debug "the code didn't arrive" complaints
without poking around in shell. Read-only with respect to user data;
the only side effect is sending one test email when ``--to`` is given.
"""
from __future__ import annotations

import smtplib
import socket
from contextlib import closing

from django.conf import settings
from django.core.management.base import BaseCommand

from notifications.models import EmailNotification
from notifications.services.email_service import EmailService


def _smtp_handshake() -> tuple[bool, str]:
    """Try opening the configured SMTP connection. Returns ``(ok, detail)``."""
    host = getattr(settings, "EMAIL_HOST", "")
    port = int(getattr(settings, "EMAIL_PORT", 587) or 587)
    use_tls = bool(getattr(settings, "EMAIL_USE_TLS", False))
    use_ssl = bool(getattr(settings, "EMAIL_USE_SSL", False))
    user = getattr(settings, "EMAIL_HOST_USER", "")
    password = getattr(settings, "EMAIL_HOST_PASSWORD", "")
    timeout = 10
    if not host:
        return False, "EMAIL_HOST is empty — server has no SMTP target"
    try:
        if use_ssl:
            client = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            client = smtplib.SMTP(host, port, timeout=timeout)
        with closing(client):
            client.ehlo()
            if use_tls and not use_ssl:
                client.starttls()
                client.ehlo()
            if user and password:
                client.login(user, password)
                return True, f"Authenticated as {user} on {host}:{port}"
            return True, f"Connected to {host}:{port} (no auth attempted — EMAIL_HOST_USER/PASSWORD empty)"
    except smtplib.SMTPAuthenticationError as exc:
        return False, f"Auth failed: {exc.smtp_code} {exc.smtp_error!r}"
    except socket.gaierror as exc:
        return False, f"DNS resolution failed for {host!r}: {exc}"
    except (socket.timeout, ConnectionError) as exc:
        return False, f"Connection error to {host}:{port}: {exc}"
    except Exception as exc:
        return False, f"Unexpected error: {type(exc).__name__}: {exc}"


class Command(BaseCommand):
    help = "End-to-end SMTP / verification email diagnostic."

    def add_arguments(self, parser):
        parser.add_argument(
            "--to", default="",
            help="Recipient for an actual test email. Omit to skip sending.",
        )

    def handle(self, *args, **opts):
        backend = getattr(settings, "EMAIL_BACKEND", "")
        host = getattr(settings, "EMAIL_HOST", "")
        port = getattr(settings, "EMAIL_PORT", "")
        use_tls = getattr(settings, "EMAIL_USE_TLS", "")
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")
        user = getattr(settings, "EMAIL_HOST_USER", "")

        self.stdout.write(self.style.NOTICE("=== Email config ==="))
        self.stdout.write(f"EMAIL_BACKEND        : {backend}")
        self.stdout.write(f"EMAIL_HOST           : {host}")
        self.stdout.write(f"EMAIL_PORT           : {port}")
        self.stdout.write(f"EMAIL_USE_TLS        : {use_tls}")
        self.stdout.write(f"EMAIL_HOST_USER      : {user}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL   : {from_email}")
        self.stdout.write("")

        if "smtp" not in (backend or "").lower():
            self.stdout.write(self.style.WARNING(
                "EMAIL_BACKEND is not SMTP — emails won't leave the server. "
                "Set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend "
                "in your .env file."
            ))

        self.stdout.write(self.style.NOTICE("=== SMTP handshake ==="))
        ok, detail = _smtp_handshake()
        marker = self.style.SUCCESS if ok else self.style.ERROR
        self.stdout.write(marker(detail))
        self.stdout.write("")

        if opts.get("to"):
            self.stdout.write(self.style.NOTICE("=== Live test send ==="))
            recipient = opts["to"].strip()
            html = (
                "<p>Hello from Onlenco — this is a test from "
                "<code>email_smtp_check</code>.</p>"
                "<p>If you received this, SMTP delivery is working.</p>"
            )
            text = "Hello from Onlenco — this is a test from email_smtp_check.\n\n" \
                   "If you received this, SMTP delivery is working."
            result = EmailService().send_email(
                recipient_email=recipient,
                subject="Onlenco — SMTP test",
                html_body=html,
                text_body=text,
            )
            marker = self.style.SUCCESS if result.success else self.style.ERROR
            self.stdout.write(marker(f"Send result: success={result.success} detail={result.detail!r}"))
            if result.success:
                self.stdout.write("Reminder: check the recipient's SPAM folder if the inbox is empty.")
            self.stdout.write("")

        self.stdout.write(self.style.NOTICE("=== Last 5 verification emails ==="))
        rows = EmailNotification.objects.filter(
            event__event_type="email_verification",
        ).order_by("-created_at")[:5]
        if not rows:
            self.stdout.write("(none)")
        for em in rows:
            self.stdout.write(
                f"  {em.created_at:%Y-%m-%d %H:%M}  "
                f"status={em.status}  attempts={em.attempts_count}  "
                f"to={em.recipient_email}  err={(em.error_message or '')[:60]}"
            )

        self.stdout.write("")
        self.stdout.write(self.style.NOTICE("=== Deliverability tips ==="))
        self.stdout.write("If status is 'sent' but users don't receive:")
        self.stdout.write("  1. SPF record on your sending domain (Hostinger DNS panel).")
        self.stdout.write("  2. DKIM enabled + key published.")
        self.stdout.write("  3. DMARC policy (start with p=none for monitoring).")
        self.stdout.write("  4. Test via https://www.mail-tester.com — get a free score.")
        self.stdout.write("  5. Ask users to check spam / 'All Mail' on Gmail.")
