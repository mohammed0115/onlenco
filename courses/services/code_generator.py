"""Centralised generator for the educational-object codes.

The codes follow a single, readable, hierarchical scheme so an admin
or a teacher can identify any row by its code alone:

    Course   ONL-A1-COURSE-001                    (per-level sequence)
    Unit     ONL-A1-C001-U02                      (course-seq + unit order)
    Lesson   ONL-A1-C001-U02-L03                  (+ lesson order)
    Quiz     ONL-A1-C001-U02-L03-QZ               (lesson code + -QZ)
    Book     ONL-A1-BOOK-001                      (per-level sequence)
    Chapter  ONL-A1-BOOK-001-CH02                 (book code + -CHnn)

The spec sketches Unit/Lesson as ``ONL-A1-U01`` / ``ONL-A1-U01-L01``
without a course sequence. That works for the "one canonical course
per level" pattern, but breaks ``unique=True`` the moment a second A1
course appears, so we embed the course sequence (``C001``) to keep
codes globally unique while staying short and readable.

Everything here is pure: no DB writes, no model imports. The model's
``save()`` (and the data migration that backfills old rows) supply
the inputs.
"""
from __future__ import annotations

import re
from typing import Iterable


# ---------------------------------------------------------------------------
# Format functions
# ---------------------------------------------------------------------------

def generate_course_code(level_code: str, seq: int) -> str:
    """``ONL-A1-COURSE-001``"""
    return f"ONL-{level_code.upper()}-COURSE-{seq:03d}"


def generate_unit_code(level_code: str, course_seq: int, unit_order: int) -> str:
    """``ONL-A1-C001-U02``"""
    return f"ONL-{level_code.upper()}-C{course_seq:03d}-U{unit_order:02d}"


def generate_lesson_code(
    level_code: str, course_seq: int, unit_order: int, lesson_order: int,
) -> str:
    """``ONL-A1-C001-U02-L03``"""
    return (
        f"ONL-{level_code.upper()}-C{course_seq:03d}"
        f"-U{unit_order:02d}-L{lesson_order:02d}"
    )


def generate_quiz_code(lesson_code: str) -> str:
    """``<lesson_code>-QZ``"""
    return f"{lesson_code}-QZ"


def generate_book_code(level_code: str, seq: int) -> str:
    """``ONL-A1-BOOK-001``"""
    return f"ONL-{level_code.upper()}-BOOK-{seq:03d}"


def generate_chapter_code(book_code: str, chapter_order: int) -> str:
    """``<book_code>-CH02``"""
    return f"{book_code}-CH{chapter_order:02d}"


# Fallbacks for orphan rows (a Lesson without a unit, a Quiz whose
# lesson somehow has no code yet). These keep ``unique=True`` happy
# during the back-fill data migration on legacy data.
def fallback_lesson_code(pk: int, level_code: str = "") -> str:
    return f"ONL-{(level_code or 'XX').upper()}-LESSON-{int(pk):06d}"


def fallback_quiz_code(pk: int) -> str:
    return f"ONL-QUIZ-{int(pk):06d}"


# ---------------------------------------------------------------------------
# Sequence helpers
# ---------------------------------------------------------------------------

_COURSE_SEQ_RE = re.compile(r"-COURSE-(\d+)$")
_BOOK_SEQ_RE = re.compile(r"-BOOK-(\d+)$")


def parse_course_sequence(course_code: str) -> int:
    """Pull the ``NNN`` out of ``ONL-XX-COURSE-NNN``. Returns 0 if the
    string doesn't match the pattern (e.g. a fallback code)."""
    m = _COURSE_SEQ_RE.search(course_code or "")
    return int(m.group(1)) if m else 0


def next_course_sequence(existing_codes: Iterable[str]) -> int:
    """Given the codes already taken at a CEFR level, return the next
    free ``NNN`` for that level."""
    return _next_sequence(existing_codes, _COURSE_SEQ_RE)


def next_book_sequence(existing_codes: Iterable[str]) -> int:
    return _next_sequence(existing_codes, _BOOK_SEQ_RE)


def _next_sequence(existing_codes: Iterable[str], regex: re.Pattern) -> int:
    """``max(existing matches) + 1``. Holes (deleted rows) are tolerated —
    we always pick the highest seen number + 1, never reuse."""
    max_n = 0
    for c in existing_codes:
        m = regex.search(c or "")
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return max_n + 1
