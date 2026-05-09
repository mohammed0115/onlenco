"""Shared persistence + reporting plumbing for all task builders.

Each builder is a generator yielding raw example dicts; this module
takes that stream and:
  1. Runs the quality filter (clean + reject + hash).
  2. Drops duplicates by content_hash (DB + within-batch).
  3. Bulk-creates AITrainingExample rows.
  4. Updates the parent DatasetBuild + writes a DatasetQualityReport.
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from . import dataset_quality_filter as qfilter
from ..models import (
    AITrainingExample,
    DatasetBuild,
    DatasetQualityReport,
)
from .. import constants as C

logger = logging.getLogger(__name__)

CHUNK = 500


def _to_model(example: dict, *, build_id: int) -> AITrainingExample:
    md = dict(example.get("metadata") or {})
    md["build_id"] = build_id
    return AITrainingExample(
        task_type=example["task_type"],
        input=example.get("input") or {},
        output=example.get("output") or {},
        source_type=example.get("source_type") or "",
        source_id=example.get("source_id"),
        cefr_level=example.get("cefr_level") or "",
        skill=example.get("skill") or "",
        quality_score=int(example.get("quality_score") or 0),
        is_approved=True,
        language=example.get("language") or "en",
        content_hash=example["content_hash"],
        metadata=md,
    )


def persist_stream(
    build: DatasetBuild,
    candidates: Iterable[dict],
    *,
    min_quality: int = 60,
    require_cefr: bool = False,
) -> dict:
    """Drive the candidate stream through filter → dedup → bulk_create.
    Returns counters used by both the build row and the quality report."""

    accepted_buf: list[dict] = []
    seen_hashes: set[str] = set()

    rejected = 0
    duplicates = 0
    private_data_hits = 0
    low_quality_dropped = 0
    cefr_counter: Counter = Counter()
    skill_counter: Counter = Counter()
    quality_total = 0
    issues: list[str] = []

    def _flush():
        nonlocal accepted_buf
        if not accepted_buf:
            return
        # DB-level dedup (against rows from previous builds + same task).
        hashes = [it["content_hash"] for it in accepted_buf]
        existing = set(
            AITrainingExample.objects
            .filter(task_type=build.task_type, content_hash__in=hashes)
            .values_list("content_hash", flat=True)
        )
        new = [it for it in accepted_buf if it["content_hash"] not in existing]
        nonlocal duplicates
        duplicates += len(accepted_buf) - len(new)
        instances = [_to_model(it, build_id=build.id) for it in new]
        with transaction.atomic():
            AITrainingExample.objects.bulk_create(
                instances, batch_size=CHUNK, ignore_conflicts=True,
            )
        accepted_buf = []

    for raw in candidates:
        cleaned, reasons = qfilter.clean_and_filter(
            raw, min_quality=min_quality, require_cefr=require_cefr,
        )
        if cleaned is None:
            rejected += 1
            if qfilter.REASON_LOW_QUALITY in reasons:
                low_quality_dropped += 1
            elif qfilter.REASON_PRIVATE_DATA in reasons:
                private_data_hits += 1
            elif reasons:
                issues.append(reasons[0])
            continue

        if qfilter.REASON_PRIVATE_DATA in reasons:
            private_data_hits += 1  # cleaned but had PII — still count

        h = cleaned["content_hash"]
        if h in seen_hashes:
            duplicates += 1
            continue
        seen_hashes.add(h)

        cefr_counter[cleaned.get("cefr_level") or ""] += 1
        skill_counter[cleaned.get("skill") or ""] += 1
        quality_total += int(cleaned.get("quality_score") or 0)
        accepted_buf.append(cleaned)

        if len(accepted_buf) >= CHUNK:
            _flush()
    _flush()

    # Final accepted = rows committed for this build.
    accepted = AITrainingExample.objects.filter(
        task_type=build.task_type, metadata__build_id=build.id,
    ).count()

    avg_quality = (quality_total / accepted) if accepted else 0.0

    build.example_count   = accepted
    build.rejected_count  = rejected
    build.duplicate_count = duplicates
    build.private_data_count = private_data_hits
    build.save(update_fields=[
        "example_count", "rejected_count",
        "duplicate_count", "private_data_count",
    ])

    DatasetQualityReport.objects.update_or_create(
        build=build,
        defaults={
            "total_examples":            accepted,
            "avg_quality_score":         round(avg_quality, 2),
            "distribution_by_cefr":      dict(cefr_counter),
            "distribution_by_skill":     dict(skill_counter),
            "distribution_by_task_type": {build.task_type: accepted},
            "duplicates_removed":        duplicates,
            "private_data_filtered":     private_data_hits,
            "low_quality_filtered":      low_quality_dropped,
            "issues":                    issues[:50],  # keep cap so JSON stays small
        },
    )

    return {
        "accepted":            accepted,
        "rejected":            rejected,
        "duplicates":          duplicates,
        "private_data_hits":   private_data_hits,
        "low_quality_dropped": low_quality_dropped,
    }


def finalise_build(build: DatasetBuild, *, status: str,
                   error_message: str = "") -> DatasetBuild:
    build.status = status
    build.error_message = error_message[:500] if error_message else ""
    build.completed_at = timezone.now()
    build.save(update_fields=["status", "error_message", "completed_at"])
    return build
