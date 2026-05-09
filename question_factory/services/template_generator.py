"""Template-only generator: blueprint × variable bindings → GeneratedQuestion.

This is the cheap path. No AI. Deterministic. Use for the bulk of
generation; reserve the AI path for items the rule validator can't handle
(open writing/speaking prompts, idiomatic explanations, etc.)."""
from __future__ import annotations

import logging
import uuid
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from . import duplicate_detector, question_renderer, question_validator
from .variable_expander import sample_bindings
from .. import constants as C
from ..models import (
    GeneratedQuestion,
    GenerationBatch,
    QuestionBlueprint,
)

logger = logging.getLogger(__name__)


def _new_batch_id(prefix: str = "qftpl") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _to_model(item: dict) -> GeneratedQuestion:
    return GeneratedQuestion(
        blueprint_id=item.get("blueprint_id"),
        code=item["code"],
        cefr_level=item.get("cefr_level") or "",
        skill=item.get("skill") or "",
        question_type=item["question_type"],
        grammar_topic_id=item.get("grammar_topic_id"),
        vocabulary_topic=item.get("vocabulary_topic") or "",
        difficulty_score=float(item.get("difficulty_score") or 0.5),
        question_text=item["question_text"],
        options=item.get("options") or [],
        correct_answer=item.get("correct_answer", ""),
        acceptable_answers=item.get("acceptable_answers") or [],
        explanation=item.get("explanation", ""),
        feedback_correct=item.get("feedback_correct", ""),
        feedback_wrong=item.get("feedback_wrong", ""),
        generated_by=item.get("generated_by", C.GEN_TEMPLATE),
        quality_score=int(item.get("quality_score") or 0),
        content_hash=item["content_hash"],
        is_active=item.get("is_active", True),
        is_reviewed=item.get("is_reviewed", False),
        approved_for_training=item.get("approved_for_training", False),
        metadata=item.get("metadata") or {},
    )


def render_for_blueprint(
    blueprint: QuestionBlueprint, *, count: int, start_variant: int = 0,
) -> list[dict]:
    """Render `count` candidate dicts (no DB writes, no validation)."""
    bindings = sample_bindings(
        blueprint.variables_schema or {},
        n=count, seed_token=blueprint.code, start_variant=start_variant,
    )
    out: list[dict] = []
    for i, binding in enumerate(bindings):
        try:
            out.append(question_renderer.render(
                blueprint, binding, variant=start_variant + i,
            ))
        except Exception as e:
            logger.warning("template render failed for %s: %s", blueprint.code, e)
    return out


def generate_for_blueprint(
    blueprint: QuestionBlueprint,
    *,
    count: int,
    start_variant: int = 0,
    quality_threshold: int = 60,
    batch: GenerationBatch | None = None,
) -> dict:
    """Render → validate → dedup → bulk_create. Returns stats dict."""
    candidates = render_for_blueprint(
        blueprint, count=count, start_variant=start_variant,
    )

    # Validate + annotate.
    accepted: list[dict] = []
    rejected = 0
    for it in candidates:
        question_validator.annotate(it)
        if question_validator.passes(it, threshold=quality_threshold):
            accepted.append(it)
        else:
            rejected += 1

    # DB-level dedup.
    new_items, dup_count = duplicate_detector.bulk_filter_new(accepted)
    # Within-chunk dedup.
    seen, deduped = set(), []
    for it in new_items:
        h = it["content_hash"]
        if h in seen:
            dup_count += 1
            continue
        seen.add(h)
        deduped.append(it)

    instances = [_to_model(it) for it in deduped]
    written = 0
    if instances:
        with transaction.atomic():
            GeneratedQuestion.objects.bulk_create(
                instances, batch_size=500, ignore_conflicts=True,
            )
        written = len(instances)

    if batch is not None:
        batch.generated_count += len(candidates)
        batch.accepted_count  += written
        batch.rejected_count  += rejected
        batch.duplicate_count += dup_count
        batch.save(update_fields=[
            "generated_count", "accepted_count",
            "rejected_count", "duplicate_count",
        ])

    return {
        "candidates": len(candidates),
        "accepted":   written,
        "rejected":   rejected,
        "duplicates": dup_count,
    }


def generate_to_target(
    *,
    target_count: int,
    cefr_level: str | None = None,
    skill: str | None = None,
    quality_threshold: int = 60,
    chunk_size: int = 200,
) -> GenerationBatch:
    """Iterate over matching blueprints round-robin until target reached."""
    blueprints = QuestionBlueprint.objects.filter(
        is_active=True, generation_strategy=C.GEN_TEMPLATE,
    )
    if cefr_level:
        blueprints = blueprints.filter(cefr_level=cefr_level)
    if skill:
        blueprints = blueprints.filter(skill=skill)
    blueprints = list(blueprints)

    batch = GenerationBatch.objects.create(
        batch_id=_new_batch_id(),
        target_count=target_count,
        status=C.BATCH_RUNNING,
        strategy=C.GEN_TEMPLATE,
        cefr_level=cefr_level or "",
        skill=skill or "",
    )

    if not blueprints:
        batch.status = C.BATCH_FAILED
        batch.error_message = "No active template blueprints match the filters."
        batch.completed_at = timezone.now()
        batch.save(update_fields=["status", "error_message", "completed_at"])
        return batch

    variant = 0
    try:
        while batch.accepted_count < target_count:
            progressed = False
            for bp in blueprints:
                if batch.accepted_count >= target_count:
                    break
                this_chunk = min(chunk_size, target_count - batch.accepted_count)
                stats = generate_for_blueprint(
                    bp, count=this_chunk, start_variant=variant,
                    quality_threshold=quality_threshold, batch=batch,
                )
                if stats["accepted"] > 0:
                    progressed = True
            variant += 1
            if not progressed:
                # Template space exhausted.
                break
        batch.status = C.BATCH_COMPLETED
    except Exception as e:
        logger.exception("template generation crashed: %s", e)
        batch.status = C.BATCH_FAILED
        batch.error_message = str(e)[:500]
    batch.completed_at = timezone.now()
    batch.save(update_fields=["status", "completed_at", "error_message"])
    return batch
