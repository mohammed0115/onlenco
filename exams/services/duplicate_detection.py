"""Duplicate detection for question-bank items.

Strategy:
    1. Normalise text (lowercase, collapse whitespace, strip punctuation).
    2. SHA-1 the normalised text → `text_hash`. Indexed on AdaptiveExercise
       so a millisecond uniqueness check is a single indexed lookup.
    3. For finer-grain "near duplicate" detection (same answer + same skill
       + similar text), expose `find_near_duplicates(item)` that callers
       can run async without holding the bulk-generate hot path.
"""
from __future__ import annotations

import hashlib
import re

from learning_core.models import AdaptiveExercise

_PUNCT_RE = re.compile(r"[^A-Za-z0-9\s؀-ۿ]+")
_WS_RE = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """Lower-case, strip punctuation, collapse whitespace. Keeps Arabic
    code points intact so AR/EN bank items dedupe correctly."""
    if not text:
        return ""
    s = text.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def hash_text(text: str) -> str:
    return hashlib.sha1(normalise_text(text).encode("utf-8")).hexdigest()


def is_duplicate(text_hash: str, exclude_pk: int | None = None) -> bool:
    qs = AdaptiveExercise.objects.filter(text_hash=text_hash)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def find_near_duplicates(item: AdaptiveExercise, limit: int = 10) -> list:
    """Return up to `limit` items in the same skill+level with the same
    correct answer. Cheap proxy for "similar question"."""
    qs = (
        AdaptiveExercise.objects
        .exclude(pk=item.pk)
        .filter(
            cefr_level=item.cefr_level,
            skill_id=item.skill_id,
            correct_answer=item.correct_answer,
        )
    )
    return list(qs[:limit])


def bulk_filter_new(items: list[dict]) -> tuple[list[dict], int]:
    """Given a list of candidate item dicts (each with `text_hash`),
    returns (new_items, dup_count). Single indexed query, no per-item
    SELECT, safe for batches of thousands."""
    hashes = {it["text_hash"] for it in items if it.get("text_hash")}
    if not hashes:
        return items, 0
    seen = set(
        AdaptiveExercise.objects
        .filter(text_hash__in=hashes)
        .values_list("text_hash", flat=True)
    )
    out = [it for it in items if it.get("text_hash") not in seen]
    return out, len(items) - len(out)
