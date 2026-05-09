"""Orchestrates a bulk run: many blueprints, many strategies, quotas
per (CEFR level × skill), AI cost cap, resume, dry-run.

Why this is a separate module from `template_generator`:
- `template_generator.generate_to_target` is good for "generate N items
  from any matching blueprint" — useful for tests and small jobs.
- This module owns the **distribution**: it knows the spec's per-level
  and per-skill quotas, switches strategies on failure, and respects
  an AI-call budget across the whole run.

Memory-safety:
- Quotas are a small dict (≤49 cells).
- Each chunk renders ≤ batch_size items, validates, dedups, persists,
  then is dropped before the next chunk.
- We never load all GeneratedQuestion rows — DB-backed `count()` gives
  per-cell progress.

Resumability:
- Same `target_count + filters` → same per-cell quotas.
- Per-cell progress comes from `count(cefr_level=L, skill=s)` so the
  loop naturally skips cells that are already full.
- A `GenerationBatch` row is created (or reused with --resume) so the
  human operator can audit exactly what ran.

Idempotency:
- `content_hash` is the truth-source. Even if the unique `code`
  collides, `bulk_create(ignore_conflicts=True)` + the dedup query
  prevent duplicate rows on rerun.
"""
from __future__ import annotations

import logging
import uuid
from typing import Callable, Optional

from django.db import transaction
from django.utils import timezone

from . import (
    ai_generator,
    duplicate_detector,
    hybrid_generator,
    question_validator,
    template_generator,
)
from .. import constants as C
from ..models import (
    GeneratedQuestion,
    GenerationBatch,
    QuestionBlueprint,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default distribution from the spec
# ---------------------------------------------------------------------------

DEFAULT_LEVEL_QUOTA = {
    "A0":  5_000,
    "A1": 15_000,
    "A2": 20_000,
    "B1": 25_000,
    "B2": 20_000,
    "C1": 10_000,
    "C2":  5_000,
}  # sums to 100k

DEFAULT_SKILL_RATIO = {
    C.SKILL_GRAMMAR:       0.25,
    C.SKILL_VOCABULARY:    0.25,
    C.SKILL_READING:       0.15,
    C.SKILL_LISTENING:     0.10,
    C.SKILL_WRITING:       0.10,
    C.SKILL_SPEAKING:      0.10,
    C.SKILL_PRONUNCIATION: 0.05,
}  # sums to 1.0

CEFR_LEVELS = list(DEFAULT_LEVEL_QUOTA.keys())


# ---------------------------------------------------------------------------
# Quota computation
# ---------------------------------------------------------------------------

def compute_quotas(
    target_count: int, *,
    cefr_level: str | None = None,
    skill: str | None = None,
) -> dict[tuple[str, str], int]:
    """Return {(level, skill): n} that sums to ≈ `target_count`.

    The default-level proportions and skill ratios always apply unless
    a filter narrows the grid to a single row/column."""
    quotas: dict[tuple[str, str], int] = {}

    levels = [cefr_level] if cefr_level else CEFR_LEVELS
    skills = [skill] if skill else list(DEFAULT_SKILL_RATIO.keys())

    if cefr_level and skill:
        quotas[(cefr_level, skill)] = target_count
        return quotas

    if cefr_level:
        # All skills at one level → split target by skill ratio.
        for s in skills:
            quotas[(cefr_level, s)] = round(target_count * DEFAULT_SKILL_RATIO[s])
    elif skill:
        # All levels at one skill → split by level proportion.
        total_level = sum(DEFAULT_LEVEL_QUOTA.values())
        for L in levels:
            quotas[(L, skill)] = round(
                target_count * DEFAULT_LEVEL_QUOTA[L] / total_level,
            )
    else:
        total_level = sum(DEFAULT_LEVEL_QUOTA.values())
        for L in levels:
            level_share = (DEFAULT_LEVEL_QUOTA[L] / total_level) * target_count
            for s in skills:
                quotas[(L, s)] = round(level_share * DEFAULT_SKILL_RATIO[s])

    # Drop zero-cells.
    return {k: v for k, v in quotas.items() if v > 0}


# ---------------------------------------------------------------------------
# AI budget tracker
# ---------------------------------------------------------------------------

class AIBudget:
    """Cap on total AI calls in the run. `0` means uncapped (no AI cost).
    `-1` means unlimited (use freely)."""
    def __init__(self, cap: int):
        self.cap = cap
        self.spent = 0

    @property
    def has_quota(self) -> bool:
        if self.cap < 0:
            return True
        return self.spent < self.cap

    def spend(self, n: int = 1) -> None:
        self.spent += max(0, n)


# ---------------------------------------------------------------------------
# Per-chunk dispatch
# ---------------------------------------------------------------------------

def _dry_run_chunk(blueprint: QuestionBlueprint, count: int,
                   *, start_variant: int, quality_threshold: int) -> dict:
    """Render + validate + dedup-check WITHOUT writing. Returns the
    same stats shape generate_for_blueprint emits, with `accepted`
    meaning "would have been written"."""
    candidates = template_generator.render_for_blueprint(
        blueprint, count=count, start_variant=start_variant,
    )
    accepted: list[dict] = []
    rejected = 0
    for it in candidates:
        question_validator.annotate(it)
        if question_validator.passes(it, threshold=quality_threshold):
            accepted.append(it)
        else:
            rejected += 1
    new_items, dup_count = duplicate_detector.bulk_filter_new(accepted)
    seen, deduped = set(), []
    for it in new_items:
        h = it["content_hash"]
        if h in seen:
            dup_count += 1
            continue
        seen.add(h)
        deduped.append(it)
    return {
        "candidates": len(candidates),
        "accepted":   len(deduped),
        "rejected":   rejected,
        "duplicates": dup_count,
    }


def _generate_one_chunk(
    blueprint: QuestionBlueprint, count: int, *,
    strategy: str,
    start_variant: int,
    quality_threshold: int,
    ai_budget: AIBudget,
    review_required: bool,
    batch: GenerationBatch,
    dry_run: bool,
) -> dict:
    """One-chunk dispatch with strategy selection + AI fallback to template."""
    if dry_run:
        return _dry_run_chunk(
            blueprint, count, start_variant=start_variant,
            quality_threshold=quality_threshold,
        )

    # Decide effective strategy given the AI budget.
    eff = strategy
    if eff in (C.GEN_AI, C.GEN_HYBRID) and not ai_budget.has_quota:
        eff = C.GEN_TEMPLATE  # AI budget exhausted → degrade to template

    if eff == C.GEN_AI:
        try:
            stats = ai_generator.generate_for_blueprint(
                blueprint, count=count,
                quality_threshold=quality_threshold, batch=None,
            )
            ai_budget.spend(1)
            if stats["accepted"] > 0 or stats.get("candidates", 0) > 0:
                stats["effective_strategy"] = C.GEN_AI
                return stats
        except Exception as e:
            logger.warning("AI generation failed for %s: %s — falling back",
                           blueprint.code, e)
        # Fall through → template fallback.
        stats = template_generator.generate_for_blueprint(
            blueprint, count=count, start_variant=start_variant,
            quality_threshold=quality_threshold, batch=None,
        )
        stats["effective_strategy"] = f"{C.GEN_TEMPLATE} (ai fallback)"
        return stats

    if eff == C.GEN_HYBRID:
        try:
            stats = hybrid_generator.generate_for_blueprint(
                blueprint, count=count, start_variant=start_variant,
                quality_threshold=quality_threshold, batch=None,
            )
            ai_budget.spend(stats.get("ai_used", 0))
            stats["effective_strategy"] = C.GEN_HYBRID
            return stats
        except Exception as e:
            logger.warning("Hybrid failed for %s: %s — falling back",
                           blueprint.code, e)
            stats = template_generator.generate_for_blueprint(
                blueprint, count=count, start_variant=start_variant,
                quality_threshold=quality_threshold, batch=None,
            )
            stats["effective_strategy"] = f"{C.GEN_TEMPLATE} (hybrid fallback)"
            return stats

    # Default: template
    stats = template_generator.generate_for_blueprint(
        blueprint, count=count, start_variant=start_variant,
        quality_threshold=quality_threshold, batch=None,
    )
    stats["effective_strategy"] = C.GEN_TEMPLATE
    return stats


# ---------------------------------------------------------------------------
# Review-required post-processing
# ---------------------------------------------------------------------------

def _post_process_review_required(batch: GenerationBatch,
                                  threshold: int) -> int:
    """When --review-required is set, items below threshold should NOT be
    inactivated — they should sit in the review queue. The generators
    already reject sub-threshold items, so we relax the threshold here:
    re-import the lower-quality candidates by lowering the floor.

    Implementation: items in the staging table with quality_score in
    [40, threshold) → flip is_active=False, is_reviewed=False, mark
    metadata.review_required=True so reviewers can find them.

    Returns the number of items flipped."""
    qs = GeneratedQuestion.objects.filter(
        quality_score__gte=40,
        quality_score__lt=threshold,
        is_active=True,
        is_reviewed=False,
    )
    flipped = 0
    for item in qs.iterator(chunk_size=500):
        md = item.metadata or {}
        md["review_required"] = True
        item.metadata = md
        item.save(update_fields=["metadata"])
        flipped += 1
    return flipped


# ---------------------------------------------------------------------------
# Resume helpers
# ---------------------------------------------------------------------------

def _new_batch_id() -> str:
    return f"qfbulk_{uuid.uuid4().hex[:10]}"


def _find_or_create_batch(*, target: int, strategy: str, cefr_level: str,
                          skill: str, resume: bool) -> GenerationBatch:
    if resume:
        b = (
            GenerationBatch.objects
            .filter(
                strategy=strategy, cefr_level=cefr_level, skill=skill,
                status__in=[C.BATCH_RUNNING, C.BATCH_PAUSED, C.BATCH_FAILED],
            )
            .order_by("-started_at")
            .first()
        )
        if b is not None:
            b.status = C.BATCH_RUNNING
            b.target_count = target
            b.error_message = ""
            b.completed_at = None
            b.save(update_fields=[
                "status", "target_count", "error_message", "completed_at",
            ])
            return b
    return GenerationBatch.objects.create(
        batch_id=_new_batch_id(),
        target_count=target,
        status=C.BATCH_RUNNING,
        strategy=strategy,
        cefr_level=cefr_level,
        skill=skill,
    )


# ---------------------------------------------------------------------------
# Public driver
# ---------------------------------------------------------------------------

def run_generation(
    *,
    target_count: int,
    batch_size: int = 500,
    strategy: str = C.GEN_TEMPLATE,
    cefr_level: str | None = None,
    skill: str | None = None,
    question_type: str | None = None,
    quality_threshold: int = 60,
    max_ai_calls: int = 0,
    review_required: bool = False,
    resume: bool = False,
    dry_run: bool = False,
    progress_cb: Optional[Callable] = None,
) -> GenerationBatch:
    """Drive a bulk generation run. Returns the GenerationBatch row.

    The returned batch carries the running totals; in dry-run mode no
    GeneratedQuestion rows are written but the batch row IS persisted
    so operators can review what would have happened."""
    quotas = compute_quotas(
        target_count, cefr_level=cefr_level, skill=skill,
    )

    batch = _find_or_create_batch(
        target=target_count, strategy=strategy,
        cefr_level=cefr_level or "", skill=skill or "",
        resume=resume,
    )
    batch.metadata = {
        **(batch.metadata or {}),
        "quotas": {f"{k[0]}/{k[1]}": v for k, v in quotas.items()},
        "dry_run": dry_run,
        "quality_threshold": quality_threshold,
        "max_ai_calls": max_ai_calls,
        "review_required_flag": review_required,
        "question_type_filter": question_type or "",
    }
    batch.save(update_fields=["metadata"])

    # AI budget; -1 sentinel = unlimited.
    if max_ai_calls is None or max_ai_calls < 0:
        ai_budget = AIBudget(cap=-1)
    else:
        ai_budget = AIBudget(cap=max_ai_calls)

    try:
        for (level, skill_), cell_target in quotas.items():
            blueprints_qs = QuestionBlueprint.objects.filter(
                cefr_level=level, skill=skill_, is_active=True,
            )
            if question_type:
                blueprints_qs = blueprints_qs.filter(question_type=question_type)
            blueprints = list(blueprints_qs)
            if not blueprints:
                if progress_cb:
                    progress_cb({
                        "level": level, "skill": skill_, "cell_target": cell_target,
                        "blueprints": 0, "skipped": True,
                    })
                continue

            # Resume: how many already exist for this cell?
            already = (
                GeneratedQuestion.objects
                .filter(cefr_level=level, skill=skill_)
                .count()
            )
            needed = max(0, cell_target - already)
            if needed == 0:
                if progress_cb:
                    progress_cb({
                        "level": level, "skill": skill_, "cell_target": cell_target,
                        "already": already, "skipped": True,
                    })
                continue

            # `variant_cursor` is a monotonically-increasing offset into
            # each blueprint's seed space — incrementing by `chunk` after
            # every render keeps successive windows non-overlapping.
            # Per-blueprint cursors are kept separately so blueprints with
            # smaller bank cardinality don't drag the whole cell back.
            saved_cursors = (batch.metadata or {}).get("variant_cursors", {})
            variant_cursors: dict[str, int] = {
                bp.code: int(saved_cursors.get(bp.code, 0)) for bp in blueprints
            }
            cell_accepted = 0
            no_progress_passes = 0
            while cell_accepted < needed:
                progressed = False
                for bp in blueprints:
                    if cell_accepted >= needed:
                        break
                    chunk = min(batch_size, needed - cell_accepted)
                    start = variant_cursors[bp.code]
                    stats = _generate_one_chunk(
                        bp, chunk,
                        strategy=strategy,
                        start_variant=start,
                        quality_threshold=quality_threshold,
                        ai_budget=ai_budget,
                        review_required=review_required,
                        batch=batch,
                        dry_run=dry_run,
                    )
                    variant_cursors[bp.code] = start + chunk
                    cell_accepted += stats.get("accepted", 0)
                    # Update the batch row.
                    batch.generated_count += stats.get("candidates", 0)
                    batch.accepted_count  += stats.get("accepted", 0)
                    batch.rejected_count  += stats.get("rejected", 0)
                    batch.duplicate_count += stats.get("duplicates", 0)
                    md = batch.metadata or {}
                    md["variant_cursors"] = variant_cursors
                    batch.metadata = md
                    batch.save(update_fields=[
                        "generated_count", "accepted_count",
                        "rejected_count", "duplicate_count", "metadata",
                    ])
                    if progress_cb:
                        progress_cb({
                            "level": level, "skill": skill_,
                            "blueprint_code": bp.code,
                            "variant": start, "chunk": chunk,
                            "stats": stats,
                            "cell_accepted": cell_accepted,
                            "cell_target": needed,
                            "ai_spent": ai_budget.spent,
                            "ai_cap": ai_budget.cap,
                        })
                    if stats.get("accepted", 0) > 0:
                        progressed = True
                if not progressed:
                    no_progress_passes += 1
                    # Two consecutive zero-progress passes → the whole
                    # cell's template space is exhausted. Abandon to avoid
                    # an infinite loop.
                    if no_progress_passes >= 2:
                        break
                else:
                    no_progress_passes = 0

        # Optional post-processing for --review-required.
        if review_required and not dry_run:
            n = _post_process_review_required(batch, threshold=quality_threshold)
            md = batch.metadata or {}
            md["review_required_flipped"] = n
            batch.metadata = md
            batch.save(update_fields=["metadata"])

        batch.status = C.BATCH_COMPLETED
    except Exception as e:
        logger.exception("bulk generation crashed")
        batch.status = C.BATCH_FAILED
        batch.error_message = str(e)[:500]
    batch.completed_at = timezone.now()
    batch.save(update_fields=["status", "completed_at", "error_message"])
    return batch
