"""Stable code generator for PlacementQuestion rows.

Convention (matches the bank seeded via `seed_placement_questions`):

    Written  -> wr.<topic>.<NNN>      e.g.  wr.intro.001
    Speaking -> sp.<topic>.<NNN>      e.g.  sp.age_country.012

Where `<topic>` is the topic-bucket slug from `TOPIC_CHOICES` (intro,
grammar_fix, age_country, ...) and `<NNN>` is a zero-padded, per
(question_type, topic) sequence.

Pure functions — no DB writes, no model imports. The model's `save()`
supplies the inputs and persists the result.
"""
from __future__ import annotations

import re
from typing import Iterable


_PREFIX_BY_TYPE = {"written": "wr", "speaking": "sp"}
_FALLBACK_SLUG = "misc"


def code_prefix(question_type: str) -> str:
    """`wr` for written, `sp` for speaking, `qx` as a last resort."""
    return _PREFIX_BY_TYPE.get((question_type or "").lower(), "qx")


def topic_slug(topic: str) -> str:
    """Normalise a topic into the slug used in codes. Falls back to
    `misc` so an admin who leaves topic blank still gets a unique code."""
    return (topic or "").strip() or _FALLBACK_SLUG


def generate_question_code(question_type: str, topic: str, seq: int) -> str:
    """`wr.intro.001`, `sp.age_country.012`, etc."""
    return f"{code_prefix(question_type)}.{topic_slug(topic)}.{int(seq):03d}"


def next_question_sequence(
    existing_codes: Iterable[str], prefix: str, slug: str,
) -> int:
    """Return the next sequence after the largest existing one for the
    given `(prefix, slug)` pair. Holes from deleted rows are not reused —
    we always pick `max(existing) + 1` so codes are append-only."""
    pat = re.compile(rf"^{re.escape(prefix)}\.{re.escape(slug)}\.(\d+)$")
    max_n = 0
    for c in existing_codes:
        m = pat.match(c or "")
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return max_n + 1
