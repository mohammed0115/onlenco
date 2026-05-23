"""HTML sanitizer for teacher-authored content.

``Lesson.content_html`` is a free-form HTML field a teacher fills in
through the editor. Rendering it with the raw ``|safe`` filter turns
any malicious tag a teacher could type (``<script>``, ``onerror=…``,
javascript: URLs) into an XSS on every enrolled student. This filter
runs ``bleach.clean`` with a conservative allowlist — keeping the
formatting students actually need (paragraphs, lists, links, images,
basic emphasis) and stripping the rest.
"""
from __future__ import annotations

import bleach
from django import template
from django.utils.safestring import mark_safe


register = template.Library()


# Conservative allowlist — what a lesson body legitimately needs.
ALLOWED_TAGS = [
    "a", "abbr", "b", "blockquote", "br", "code", "div", "em", "h1", "h2",
    "h3", "h4", "h5", "h6", "hr", "i", "img", "li", "ol", "p", "pre", "span",
    "strong", "sub", "sup", "table", "tbody", "td", "th", "thead", "tr",
    "u", "ul",
]
ALLOWED_ATTRIBUTES = {
    "*": ["class", "dir", "lang", "title"],
    "a": ["href", "rel", "target"],
    "img": ["src", "alt", "width", "height"],
    "th": ["scope"],
    "td": ["colspan", "rowspan"],
}
# Only http(s) and mailto: schemes — blocks javascript:, data:text/html, …
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


@register.filter(name="safe_html", is_safe=True)
def safe_html(value):
    """Return ``value`` sanitized through bleach and marked safe.

    Use this filter on EVERY field whose HTML comes from a non-superuser
    author (lessons, course descriptions, teacher notes, etc.). Never
    pair with ``|safe`` — this filter already marks the output safe.
    """
    if not value:
        return ""
    cleaned = bleach.clean(
        str(value),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    )
    return mark_safe(cleaned)
