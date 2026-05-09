"""TemplateRenderer — picks the right HTML template + subject for an event."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from .. import constants as C
from ..models import NotificationTemplate

logger = logging.getLogger(__name__)

TEMPLATE_DIR = "notifications/emails/"


@dataclass
class RenderedEmail:
    subject: str
    html: str
    template_name: str
    language: str


class TemplateRenderer:
    def render(self, event_type: str, language: str, context: dict) -> RenderedEmail:
        # Unknown / blank language falls back to Arabic — the project
        # default. Spec rule: "If user language is unknown, default to
        # Arabic." Previously this fell back to English silently.
        language = language if language in {"en", "ar"} else "ar"

        # Override row may exist in DB.
        override = (
            NotificationTemplate.objects.filter(
                event_type=event_type, language=language, is_active=True
            ).first()
            or NotificationTemplate.objects.filter(
                event_type=event_type, language="en", is_active=True
            ).first()
        )
        if override:
            template_name = override.template_name
            subject = override.subject
            # Safety net: if an admin saved a subject that still contains
            # unresolved snake_case identifiers, run the humanizer over it
            # so we don't leak technical names to the recipient.
            if subject and "_" in subject:
                from core.services.text_humanizer import humanize_text
                subject = humanize_text(subject, language=language)
        else:
            template_name = C.TEMPLATE_NAMES.get(event_type, "base_email.html")
            # Centralised lookup — falls back across AR ↔ EN so an event
            # without an entry in one language still gets a translated
            # subject from the other rather than a raw event key.
            from .subjects import get_localized_subject
            subject = get_localized_subject(event_type, language)

        ctx = {
            **context,
            "event_type": event_type,
            "language": language,
            "dir": "rtl" if language == "ar" else "ltr",
            "lang": language,
            "subject": subject,
        }

        path = f"{TEMPLATE_DIR}{template_name}"
        try:
            html = render_to_string(path, ctx)
        except TemplateDoesNotExist:
            logger.warning("Notification template missing: %s", path)
            html = render_to_string(f"{TEMPLATE_DIR}base_email.html", ctx)
        return RenderedEmail(
            subject=subject,
            html=html,
            template_name=template_name,
            language=language,
        )
