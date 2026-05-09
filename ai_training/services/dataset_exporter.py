"""Stream training examples to JSONL or CSV.

Splits
------
The split (train / validation / test) is decided **deterministically**
from the example's `content_hash`. This means:
  * The same example always lands in the same split, even across
    rebuilds — so test-set leakage into train-set is impossible.
  * No need to materialise random shuffles.

Default split: 80% train, 10% validation, 10% test (hash mod 10).

Memory safety
-------------
- We use `qs.iterator(chunk_size=…)` so the queryset never loads
  everything into memory.
- We write rows one at a time to the sink, so the only data in memory
  is the current row.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
from typing import Iterable, IO

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from ..models import AITrainingExample, DatasetBuild, DatasetExport
from .. import constants as C

logger = logging.getLogger(__name__)

DEFAULT_TRAIN = 0.80
DEFAULT_VAL   = 0.10
# test = 1 - train - val

CHUNK = 1000


def assign_split(content_hash: str) -> str:
    """Map a content_hash to a split deterministically.

    Hash → first 8 hex digits → integer mod 100 → bucket.
    With defaults: 0–79 = train, 80–89 = validation, 90–99 = test.
    """
    bucket = int(content_hash[:8], 16) % 100
    if bucket < int(DEFAULT_TRAIN * 100):
        return C.SPLIT_TRAIN
    if bucket < int((DEFAULT_TRAIN + DEFAULT_VAL) * 100):
        return C.SPLIT_VALIDATION
    return C.SPLIT_TEST


def assign_splits(build: DatasetBuild) -> dict:
    """Walk every example in the build, set `split` based on content_hash.
    Idempotent — re-running stamps the same splits."""
    counts = {C.SPLIT_TRAIN: 0, C.SPLIT_VALIDATION: 0, C.SPLIT_TEST: 0}
    qs = AITrainingExample.objects.filter(
        metadata__build_id=build.id,
    ).only("id", "content_hash", "split")
    for row in qs.iterator(chunk_size=CHUNK):
        target = assign_split(row.content_hash)
        if row.split != target:
            AITrainingExample.objects.filter(pk=row.pk).update(split=target)
        counts[target] += 1
    return counts


def _output_path(build: DatasetBuild, fmt: str, split: str) -> str:
    base = getattr(settings, "AI_TRAINING_DIR", None)
    if not base:
        base = os.path.join(getattr(settings, "BASE_DIR", "."), "datasets", "ai_training")
    os.makedirs(base, exist_ok=True)
    ts = timezone.now().strftime("%Y%m%dT%H%M%S")
    return os.path.join(base, f"{build.name}-{split}-{ts}.{fmt}")


def _filtered_qs(build: DatasetBuild, split: str | None) -> QuerySet[AITrainingExample]:
    qs = AITrainingExample.objects.filter(
        task_type=build.task_type, is_approved=True,
        metadata__build_id=build.id,
    )
    if split and split != C.SPLIT_ALL:
        qs = qs.filter(split=split)
    return qs.order_by("id")


def _write_jsonl(qs: QuerySet[AITrainingExample], sink: IO) -> tuple[int, int]:
    rows, bytes_written = 0, 0
    for ex in qs.iterator(chunk_size=CHUNK):
        line = json.dumps({
            "task_type": ex.task_type,
            "input": ex.input,
            "output": ex.output,
            "cefr_level": ex.cefr_level,
            "skill": ex.skill,
            "quality_score": ex.quality_score,
            "split": ex.split,
            "language": ex.language,
        }, ensure_ascii=False) + "\n"
        sink.write(line)
        rows += 1
        bytes_written += len(line.encode("utf-8"))
    return rows, bytes_written


def _write_csv(qs: QuerySet[AITrainingExample], sink: IO) -> tuple[int, int]:
    writer = csv.writer(sink)
    writer.writerow([
        "task_type", "input", "output", "cefr_level",
        "skill", "quality_score", "split", "language",
    ])
    rows = 0
    counter = io.StringIO()
    counter_writer = csv.writer(counter)
    counter_writer.writerow([
        "task_type", "input", "output", "cefr_level",
        "skill", "quality_score", "split", "language",
    ])
    bytes_written = len(counter.getvalue().encode("utf-8"))
    counter.close()
    for ex in qs.iterator(chunk_size=CHUNK):
        row = [
            ex.task_type,
            json.dumps(ex.input, ensure_ascii=False),
            json.dumps(ex.output, ensure_ascii=False),
            ex.cefr_level, ex.skill, ex.quality_score,
            ex.split, ex.language,
        ]
        writer.writerow(row)
        rows += 1
        # Approximate byte count (covers the common case; close enough for monitoring).
        bytes_written += len(",".join(str(c) for c in row).encode("utf-8")) + 1
    return rows, bytes_written


def export(
    build: DatasetBuild, *,
    fmt: str = C.FORMAT_JSONL,
    split: str = C.SPLIT_ALL,
    sink: IO | None = None,
) -> DatasetExport:
    """Stream the build's examples to disk (or `sink`) and record the run."""
    job = DatasetExport.objects.create(
        build=build, format=fmt, split=split, status=C.BUILD_RUNNING,
    )
    own_sink = False
    if sink is None:
        path = _output_path(build, fmt, split)
        sink = open(path, "w", encoding="utf-8", newline="")
        own_sink = True
        job.file_path = path

    rows = 0
    bytes_written = 0
    try:
        qs = _filtered_qs(build, split)
        if fmt == C.FORMAT_JSONL:
            rows, bytes_written = _write_jsonl(qs, sink)
        elif fmt == C.FORMAT_CSV:
            rows, bytes_written = _write_csv(qs, sink)
        else:
            raise ValueError(f"Unknown format: {fmt}")
        job.status = C.BUILD_COMPLETED
    except Exception as e:
        logger.exception("dataset export crashed")
        job.status = C.BUILD_FAILED
        job.error_message = str(e)[:500]
    finally:
        if own_sink:
            sink.close()
        job.row_count = rows
        job.bytes_written = bytes_written
        job.completed_at = timezone.now()
        job.save(update_fields=[
            "status", "row_count", "bytes_written",
            "completed_at", "file_path", "error_message",
        ])
    return job
