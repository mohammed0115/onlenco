"""Publishing gate for library books (Phase 19.0E).

A single, testable rule the Platform Admin UI consults before exposing a book
to students. Keeps the copyright + completeness contract in one place so the
admin UI, the publish action, and the tests all agree.

This module is read-only: it never mutates a book. Call ``can_publish_book``,
then the caller decides whether to flip ``is_published``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Q


# Copyright statuses that require an explicit source / license trail.
_NEEDS_SOURCE = {"licensed", "school_excerpt_with_permission"}


@dataclass
class PublishCheck:
    allowed: bool
    reasons: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # truthy == publishable
        return self.allowed


def can_publish_book(book) -> PublishCheck:
    """Return whether ``book`` may be published to students, with reasons.

    Conditions (all must hold):
      1. title is not empty
      2. copyright_status is set and not "unknown"
      3. is_copyright_cleared is True
      4. the book has at least one chapter
      5. the book has at least one PUBLISHED NovelSegment
      6. no published segment has empty English text (text_en)
      7. licensed / school-excerpt books carry a source title, URL, or notes
    """
    from library.models import NovelSegment

    reasons: list[str] = []

    if not (book.title or "").strip():
        reasons.append("Book title is empty.")

    status = book.copyright_status or "unknown"
    if status == "unknown":
        reasons.append("Copyright status is still 'unknown'.")

    if not book.is_copyright_cleared:
        reasons.append("Copyright is not marked as cleared.")

    if not book.chapters.exists():
        reasons.append("Book has no chapters.")

    published_segments = NovelSegment.objects.filter(
        chapter__book=book, is_published=True,
    )
    if not published_segments.exists():
        reasons.append("Book has no published segments.")
    elif published_segments.filter(Q(text_en="") | Q(text_en__isnull=True)).exists():
        reasons.append("A published segment has empty English text.")

    if status in _NEEDS_SOURCE:
        has_source = any([
            (book.source_title or "").strip(),
            (book.source_url or "").strip(),
            (book.license_notes or "").strip(),
        ])
        if not has_source:
            reasons.append(
                "Licensed / school-excerpt books need a source title, URL, or license notes.")

    return PublishCheck(allowed=not reasons, reasons=reasons)
