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
        language = language if language in {"en", "ar"} else "en"

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
        else:
            template_name = C.TEMPLATE_NAMES.get(event_type, "base_email.html")
            subject = (
                C.SUBJECTS_AR.get(event_type)
                if language == "ar"
                else C.DEFAULT_SUBJECTS.get(event_type)
            ) or C.DEFAULT_SUBJECTS.get(event_type, "Onlenco")

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
