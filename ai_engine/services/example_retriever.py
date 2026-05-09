"""Retrieve curated training (input, output) pairs from `AITrainingExample`.

This is the canonical "in-context learning" corpus — already
quality-filtered, PII-redacted, deduplicated by `ai_training`. The
RAG layer just narrows by metadata + ranks by relevance."""
from __future__ import annotations

import logging
import re
from typing import Iterable

from ai_training.models import AITrainingExample

from .question_retriever import _embedding_score, _tokens

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def _qs(*, task_type, cefr_level, skill, only_approved=True):
    """Hard filters only — `query` is applied as a soft ranker, not a
    filter, so callers always get *some* candidates back even when the
    keyword doesn't appear verbatim."""
    qs = AITrainingExample.objects.filter(task_type=task_type)
    if only_approved:
        qs = qs.filter(is_approved=True)
    if cefr_level:
        qs = qs.filter(cefr_level=cefr_level)
    if skill:
        qs = qs.filter(skill=skill)
    return qs


def _serialise(row: AITrainingExample) -> dict:
    return {
        "source": "AITrainingExample",
        "id": row.id,
        "task_type": row.task_type,
        "cefr_level": row.cefr_level or "",
        "skill": row.skill or "",
        "input": row.input or {},
        "output": row.output or {},
        "quality_score": int(row.quality_score or 0),
        "language": row.language or "en",
        "split": row.split or "",
    }


def _row_text(row: AITrainingExample) -> str:
    """Concatenate every string leaf in input + output — used for
    keyword scoring."""
    parts: list[str] = []
    for field in (row.input or {}, row.output or {}):
        if isinstance(field, dict):
            for v in field.values():
                if isinstance(v, str):
                    parts.append(v)
                elif isinstance(v, list):
                    parts.extend(str(x) for x in v if isinstance(x, str))
    return " ".join(parts)


def _score(query_tokens: set[str], row: AITrainingExample) -> float:
    """Rank by keyword overlap across input + output."""
    if not query_tokens:
        # No query → quality_score breaks the tie deterministically.
        return (row.quality_score or 0) / 100.0
    text = _row_text(row)
    cand = {t.lower() for t in re.findall(r"[A-Za-z0-9]+", text) if len(t) > 1}
    if not cand:
        return 0.0
    overlap = len(query_tokens & cand) / len(query_tokens)
    return 2.0 * overlap + 0.5 * ((row.quality_score or 0) / 100.0)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def retrieve_examples(
    *,
    task_type: str,
    cefr_level: str | None = None,
    skill: str | None = None,
    query: str | None = None,
    limit: int = 5,
    only_approved: bool = True,
    candidate_pool: int = 50,
) -> list[dict]:
    """Return up to `limit` curated training examples for `task_type`."""
    rows = list(
        _qs(
            task_type=task_type, cefr_level=cefr_level, skill=skill,
            only_approved=only_approved,
        )
        .order_by("-quality_score", "-id")[:candidate_pool]
    )
    if not rows:
        return []
    qtokens = _tokens(query or "")
    rows.sort(key=lambda r: _score(qtokens, r), reverse=True)
    return [_serialise(r) for r in rows[:limit]]
