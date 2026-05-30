"""Small template filters used by the Onlenco quiz renderer."""
from __future__ import annotations

from django import template

register = template.Library()


@register.filter(name="split")
def split_filter(value, separator=","):
    """Split a string by a separator. Used by the quiz template to
    iterate ad-hoc lists in markup (e.g. column order)."""
    if value is None:
        return []
    return [s for s in str(value).split(separator)]


@register.filter(name="dict_get")
def dict_get(d, key):
    """Look up a key in a dict — Django templates don't have native
    `{{ d.key }}` access when the key is dynamic."""
    if not d:
        return ""
    try:
        return d.get(key, "")
    except AttributeError:
        return ""
