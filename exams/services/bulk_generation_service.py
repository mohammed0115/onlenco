"""Resumable, idempotent, deduping bulk generator for the question bank.

Pipeline per chunk:
    1. Generate `chunk_size` candidate dicts via templates (and optionally
       AI for `--max-ai-per-batch`).
    2. Compute `text_hash` (already done by generators).
    3. `bulk_filter_new` discards items already in DB by hash.
    4. Quality filter — skip items below threshold; the rest are
       written with `is_active`/`is_reviewed` set per their generator.
    5. `bulk_create(ignore_conflicts=True)` on AdaptiveExercise.
    6. Update the QuestionGenerationBatch row with progress so the
       command can resume after a crash.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import timedelta
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from learning_core.models import AdaptiveExercise

from .. import constants as C
from ..models import QuestionGenerationBatch
from .duplicate_detection import bulk_filter_new
from .question_quality import passes as quality_passes
from .template_question_generator import generate as tpl_generate

logger = logging.getLogger(__name__)

CEFR_LEVELS = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]

# Suggested distribution per the spec.
DEFAULT_LEVEL_QUOTA = {
    "A0": 20_000,
    "A1": 40_000,
    "A2": 50_000,
    "B1": 60_000,
    "B2": 60_000,
    "C1": 40_000,
    "C2": 30_000,
}


def _new_batch_id(prefix: str = "qb") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _items_for_db(items: list[dict]) -> list[AdaptiveExercise]:
    """Convert dicts to model instances. `skill_id` / `topic_id` are
    propagated when present so RAG queries that filter by skill/topic
    actually match the rows we just wrote."""
    return [
        AdaptiveExercise(
            code=it.get("code", "") or "",
            cefr_level=it["cefr_level"],
            difficulty_score=it["difficulty_score"],
            question_type=it["question_type"],
            question=it["question"],
            options=it.get("options", []),
            correct_answer=it["correct_answer"],
            explanation=it.get("explanation", ""),
            feedback_correct=it.get("feedback_correct", ""),
            feedback_wrong=it.get("feedback_wrong", ""),
            estimated_time_seconds=it.get("estimated_time_seconds", 30),
            points=it.get("points", 1),
            language=it.get("language", "en"),
            generated_by=it.get("generated_by", "template"),
            generated_by_ai=it.get("generated_by_ai", False),
            acceptable_answers=it.get("acceptable_answers", []),
            quality_score=it.get("quality_score", 0),
            is_active=it.get("is_active", True),
            is_reviewed=it.get("is_reviewed", False),
            metadata=it.get("metadata", {}),
            text_hash=it.get("text_hash", ""),
            skill_id=it.get("skill_id"),
            topic_id=it.get("topic_id"),
        )
        for it in items
    ]


def generate_chunk(
    *,
    cefr_level: str,
    skill: Optional[str] = None,
    chunk_size: int = 1000,
    use_ai: bool = False,
    max_ai_per_batch: int = 0,
    quality_threshold: int = 60,
    seed: int = 42,
    variant: int = 0,
    dry_run: bool = False,
) -> dict:
    """Generate one chunk; return a stats dict."""
    target = chunk_size

    candidates: list[dict] = tpl_generate(
        cefr_level, skill=skill, count=target, seed=seed, variant=variant,
    )

    if use_ai and max_ai_per_batch > 0:
        try:
            from .ai_question_generator import generate as ai_generate
            ai_items = ai_generate(
                cefr_level=cefr_level,
                skill=skill or "grammar",
                count=min(max_ai_per_batch, 10),
                code_prefix=f"ai_b{variant}",
            )
            candidates.extend(ai_items)
        except Exception as e:
            logger.warning("AI generation failed: %s", e)

    # Quality filter.
    passable = [c for c in candidates if quality_passes(c, threshold=quality_threshold)]

    # DB-level dedup.
    new_items, dup_count = bulk_filter_new(passable)

    # Within-chunk dedup (two templates could produce the same hash).
    seen = set()
    deduped: list[dict] = []
    for it in new_items:
        h = it.get("text_hash") or ""
        if h in seen:
            dup_count += 1
            continue
        seen.add(h)
        deduped.append(it)

    if dry_run:
        return {
            "candidates": len(candidates),
            "passed_quality": len(passable),
            "new": len(deduped),
            "duplicates": dup_count,
            "written": 0,
        }

    instances = _items_for_db(deduped)
    written = 0
    if instances:
        with transaction.atomic():
            AdaptiveExercise.objects.bulk_create(
                instances, batch_size=500, ignore_conflicts=True,
            )
        written = len(instances)
    return {
        "candidates": len(candidates),
        "passed_quality": len(passable),
        "new": len(deduped),
        "duplicates": dup_count,
        "written": written,
    }


def generate_to_target(
    *,
    target_count: int,
    cefr_level: Optional[str] = None,
    skill: Optional[str] = None,
    chunk_size: int = 1000,
    use_ai: bool = False,
    max_ai_per_batch: int = 0,
    quality_threshold: int = 60,
    resume: bool = False,
    dry_run: bool = False,
    progress_cb=None,
) -> QuestionGenerationBatch:
    """Drive generation until `target_count` rows have been written for
    the requested level/skill. Resumable across runs."""
    levels = [cefr_level] if cefr_level else CEFR_LEVELS

    batch = None
    if resume:
        batch = (
            QuestionGenerationBatch.objects
            .filter(
                cefr_level=cefr_level or "",
                skill=skill or "",
                status__in=[C.BATCH_RUNNING, C.BATCH_PAUSED, C.BATCH_FAILED],
            )
            .order_by("-started_at")
            .first()
        )
    if batch is None:
        batch = QuestionGenerationBatch.objects.create(
            batch_id=_new_batch_id(),
            target_count=target_count,
            cefr_level=cefr_level or "",
            skill=skill or "",
            status=C.BATCH_RUNNING,
        )
    else:
        batch.status = C.BATCH_RUNNING
        batch.target_count = target_count
        batch.save(update_fields=["status", "target_count"])

    variant = 0
    try:
        while batch.generated_count < target_count:
            for L in levels:
                # How much of `target_count` should this level shoulder?
                # If a single level was supplied, target == this level's quota.
                # If all levels, distribute by DEFAULT_LEVEL_QUOTA proportionally.
                if cefr_level:
                    level_target_remaining = target_count - batch.generated_count
                else:
                    quota = DEFAULT_LEVEL_QUOTA.get(L, 1)
                    total_quota = sum(DEFAULT_LEVEL_QUOTA.values())
                    level_target = int(target_count * quota / total_quota)
                    already = AdaptiveExercise.objects.filter(cefr_level=L).count()
                    level_target_remaining = max(0, level_target - already)

                if level_target_remaining <= 0:
                    continue

                this_chunk = min(chunk_size, level_target_remaining)
                stats = generate_chunk(
                    cefr_level=L, skill=skill,
                    chunk_size=this_chunk,
                    use_ai=use_ai,
                    max_ai_per_batch=max_ai_per_batch,
                    quality_threshold=quality_threshold,
                    seed=42,
                    variant=variant,
                    dry_run=dry_run,
                )
                # In dry-run mode no rows are persisted, so `written` is
                # always 0 and the loop would spin to the safety valve.
                # Treat the candidates that *would* have been written
                # (post-dedup, post-quality) as progress so dry-run
                # terminates at the requested target.
                progress = stats["new"] if dry_run else stats["written"]
                batch.generated_count += progress
                batch.duplicate_count += stats["duplicates"]
                batch.save(update_fields=["generated_count", "duplicate_count"])
                if progress_cb:
                    progress_cb(batch, stats, level=L, variant=variant)
                if batch.generated_count >= target_count:
                    break
            variant += 1
            # Safety valve — if 200 variants haven't yielded the target,
            # template space is exhausted; stop and let the operator
            # decide to enable AI generation or raise the target.
            if variant > 200:
                break
        batch.status = C.BATCH_COMPLETED
        batch.completed_at = timezone.now()
    except Exception as e:
        batch.status = C.BATCH_FAILED
        batch.error_message = str(e)[:500]
        logger.exception("bulk generation crashed: %s", e)
    batch.save(update_fields=["status", "completed_at", "error_message"])
    return batch
