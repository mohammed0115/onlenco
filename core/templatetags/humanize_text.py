"""Template filters for text humanisation / speech sanitisation.

Usage in templates:
    {% load humanize_text %}
    {{ message|humanize }}
    {{ message|humanize_speech }}
    {{ event_type|humanize_event }}
    {{ field_name|humanize_field }}
"""
from django import template
from django.utils import translation

from core.services.text_humanizer import (
    humanize_event_name,
    humanize_field_name,
    humanize_for_speech,
    humanize_text,
)


register = template.Library()


def _lang() -> str:
    code = translation.get_language() or "en"
    return "ar" if code.startswith("ar") else "en"


@register.filter(name="humanize")
def humanize_filter(value):
    return humanize_text(value, language=_lang(), mode="display")


@register.filter(name="humanize_speech")
def humanize_speech_filter(value):
    return humanize_for_speech(value, language=_lang())


@register.filter(name="humanize_event")
def humanize_event_filter(value):
    return humanize_event_name(value, language=_lang())


@register.filter(name="humanize_field")
def humanize_field_filter(value):
    return humanize_field_name(value, language=_lang())
