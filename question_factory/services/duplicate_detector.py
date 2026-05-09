"""Duplicate detection for GeneratedQuestion.

Strategy:
  1. SHA-1 hash of normalised text (lowercase, strip punctuation, collapse
     whitespace) — single indexed lookup against `content_hash`.
  2. Optional near-duplicate check: same skill + same correct answer +
     similar normalised question text (Levenshtein-like via shared word set).

This module deliberately reuses the canonical normaliser from `exams`
so that question_factory and exams compute identical hashes — meaning
items moved between the two systems dedupe correctly.
"""
from __future__ import annotations

import hashlib

from exams.services.duplicate_detection import normalise_text

from ..models import GeneratedQuestion


def hash_question(question_text: str, correct_answer: str = "") -> str:
    """SHA-1 of the normalised `question_text|correct_answer` string."""
    payload = normalise_text(question_text) + "|" + normalise_text(correct_answer)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def is_duplicate(content_hash: str, *, exclude_pk: int | None = None) -> bool:
    qs = GeneratedQuestion.objects.filter(content_hash=content_hash)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


def bulk_filter_new(items: list[dict]) -> tuple[list[dict], int]:
    """Strip items whose content_hash already exists in DB.
    Returns (new_items, duplicate_count). One indexed query, batch-safe."""
    hashes = {it["content_hash"] for it in items if it.get("content_hash")}
    if not hashes:
        return items, 0
    existing = set(
        GeneratedQuestion.objects
        .filter(content_hash__in=hashes)
        .values_list("content_hash", flat=True)
    )
    out = [it for it in items if it.get("content_hash") not in existing]
    return out, len(items) - len(out)


def find_near_duplicates(item: GeneratedQuestion, *, limit: int = 5) -> list[GeneratedQuestion]:
    """Same skill + same correct answer; cheap proxy for "looks similar"."""
    qs = (
        GeneratedQuestion.objects
        .exclude(pk=item.pk)
        .filter(skill=item.skill, correct_answer=item.correct_answer)
    )
    return list(qs[:limit])
