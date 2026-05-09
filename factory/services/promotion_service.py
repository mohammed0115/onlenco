"""Promotion: render templates → validate → bulk-promote into the live
question bank (`learning_core.AdaptiveExercise`).

Why this lives in `factory` and not `exams`:
- Generation is the factory's responsibility.
- Persistence is governed by quality + dedup (which already exist in
  exams/services). This module just wires factory → exams services.

The function is resumable + idempotent because:
- AdaptiveExercise has a partial unique constraint on `code`.
- bulk_create uses `ignore_conflicts=True`.
- text_hash is recomputed and bulk_filter_new is run before insert.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from django.db import transaction

from exams.services.duplicate_detection import bulk_filter_new, hash_text
from learning_core.models import AdaptiveExercise

from . import quality_router
from .template_engine import render_many
from .variation_generator import variations_for_topic_kind
from ..models import QuestionTemplate, Topic

logger = logging.getLogger(__name__)


def _to_model(item: dict) -> AdaptiveExercise:
    return AdaptiveExercise(
        code=item.get("code", ""),
        cefr_level=item.get("cefr_level") or "",
        difficulty_score=float(item.get("difficulty_score") or 0.5),
        question_type=item["question_type"],
        question=item["question"],
        options=item.get("options", []),
        correct_answer=item.get("correct_answer", ""),
        explanation=item.get("explanation", ""),
        feedback_correct=item.get("feedback_correct", ""),
        feedback_wrong=item.get("feedback_wrong", ""),
        estimated_time_seconds=int(item.get("estimated_time_seconds", 30)),
        points=int(item.get("points", 1)),
        language=item.get("language", "en"),
        generated_by=item.get("generated_by", "template"),
        generated_by_ai=bool(item.get("generated_by_ai", False)),
        is_active=True,
        is_reviewed=item.get("is_reviewed", True),
        acceptable_answers=item.get("acceptable_answers", []),
        quality_score=int(item.get("quality_score", 0)),
        text_hash=item.get("text_hash") or hash_text(
            (item.get("question") or "") + "|" + (item.get("correct_answer") or "")
        ),
        metadata=item.get("metadata", {}),
    )


def promote(items: Iterable[dict], *, allow_ai_validation: bool = False) -> dict:
    """Validate + dedup + bulk-create into AdaptiveExercise.

    Returns stats: {candidates, approved, rejected, duplicates, written}."""
    items = list(items)
    approved: list[dict] = []
    rejected = 0
    for it in items:
        if not it.get("text_hash"):
            it["text_hash"] = hash_text(
                (it.get("question") or "") + "|" + (it.get("correct_answer") or "")
            )
        ok, report = quality_router.validate(it, allow_ai=allow_ai_validation)
        it.setdefault("metadata", {})["quality_report"] = report
        it["quality_score"] = report.get("rule_score", 0)
        if ok:
            approved.append(it)
        else:
            rejected += 1
    new_items, dup_count = bulk_filter_new(approved)
    # Within-batch dedup.
    seen, deduped = set(), []
    for it in new_items:
        h = it.get("text_hash") or ""
        if h in seen:
            dup_count += 1
            continue
        seen.add(h)
        deduped.append(it)
    instances = [_to_model(it) for it in deduped]
    written = 0
    if instances:
        with transaction.atomic():
            AdaptiveExercise.objects.bulk_create(
                instances, batch_size=500, ignore_conflicts=True,
            )
        written = len(instances)
    return {
        "candidates":  len(items),
        "approved":    len(approved),
        "rejected":    rejected,
        "duplicates":  dup_count,
        "written":     written,
    }


def promote_template(template: QuestionTemplate, *, count: int,
                     start_variant: int = 0,
                     allow_ai_validation: bool = False) -> dict:
    """Render N items from one template and promote them."""
    items = render_many(template, count=count, start_variant=start_variant)
    return promote(items, allow_ai_validation=allow_ai_validation)


def promote_topic_kind(*, topic_kind: str, cefr_level: Optional[str] = None,
                       count: int, allow_ai_validation: bool = False) -> dict:
    """Spread N items across all templates for a kind/CEFR pair, then promote."""
    items = variations_for_topic_kind(
        topic_kind, cefr_level=cefr_level, count=count, seed=0,
    )
    return promote(items, allow_ai_validation=allow_ai_validation)
