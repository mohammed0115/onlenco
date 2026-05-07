"""Template tags for the project translation dictionary."""
from django import template
from django.utils import translation
from django.utils.safestring import mark_safe

from core.translations import DICT


register = template.Library()


def _current_lang():
    lang = translation.get_language() or "en"
    return "ar" if lang.startswith("ar") else "en"


@register.simple_tag
def t(key):
    """Look up a translation by key. Falls back to English then to the
    raw key if missing."""
    entry = DICT.get(key)
    if not entry:
        return key
    lang = _current_lang()
    return mark_safe(entry.get(lang) or entry.get("en") or key)


@register.simple_tag
def t_either(en_text, ar_text):
    """Inline switch for one-off bilingual strings that aren't in the
    dictionary (used for tiny labels)."""
    return mark_safe(ar_text if _current_lang() == "ar" else en_text)
