"""Template filters for RTL/LTR direction handling.

Load with ``{% load direction_tags %}``. Provides:

  {{ "ar"|language_dir }}              → "rtl"
  {{ "en"|language_dir }}              → "ltr"
  {{ "ar"|text_align }}                → "right"
  {{ "en"|text_align }}                → "left"
  {{ "ar"|is_rtl }}                    → True
  {{ "Onlenco"|bdi }}                  → '<bdi dir="auto">Onlenco</bdi>'
  {{ "مستواك A1 improved"|bdi_mix:"ar" }}
        → 'مستواك <bdi dir="ltr">A1</bdi> <bdi dir="ltr">improved</bdi>'

These filters are safe to apply to any string — bad input returns a
sensible default rather than raising.
"""
from __future__ import annotations

from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape

register = template.Library()


def _normalise_lang(value) -> str:
    """Coerce a language input to 'ar' or 'en'."""
    s = (str(value) if value is not None else "").strip().lower()
    if s.startswith("ar"):
        return "ar"
    return "en"


@register.filter(name="language_dir")
def language_dir(value) -> str:
    """Return ``rtl`` for Arabic, ``ltr`` otherwise.

    Use in templates as:
        <html lang="{{ lang }}" dir="{{ lang|language_dir }}">
    """
    return "rtl" if _normalise_lang(value) == "ar" else "ltr"


@register.filter(name="text_align")
def text_align(value) -> str:
    """Return ``right`` for Arabic, ``left`` otherwise.

    For inline-style helpers in email templates where you can't easily
    flip ``text-align`` via CSS classes.
    """
    return "right" if _normalise_lang(value) == "ar" else "left"


@register.filter(name="is_rtl")
def is_rtl(value) -> bool:
    """Return True when the language is Arabic-family."""
    return _normalise_lang(value) == "ar"


@register.filter(name="bdi", is_safe=True)
def bdi(value) -> str:
    """Wrap any string in ``<bdi dir="auto">…</bdi>``.

    Use for any short label that may contain Arabic OR English in
    different rendering contexts (e.g. a learner's CEFR level "A1"
    sitting inside an Arabic sentence). The browser handles direction
    via ``dir="auto"``.
    """
    safe_text = escape(str(value) if value is not None else "")
    return mark_safe(f'<bdi dir="auto">{safe_text}</bdi>')


@register.filter(name="bdi_mix", is_safe=True)
def bdi_mix(value, primary_language="ar") -> str:
    """Wrap minority-language runs in ``<bdi>`` with explicit dir.

    Delegates to ``core.services.text_humanizer.sanitize_mixed_language_text``
    so the same rules apply everywhere mixed text is rendered.

    Returns marked-safe so the wrapping tags are not escaped.
    """
    try:
        from core.services.text_humanizer import sanitize_mixed_language_text
    except Exception:
        return escape(str(value) if value is not None else "")
    if value is None:
        return ""
    out = sanitize_mixed_language_text(
        str(value), primary_language=primary_language, mode="display",
    )
    return mark_safe(out)
