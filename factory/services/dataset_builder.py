"""Stream training datasets to JSONL on disk — one row at a time.

Why JSONL on disk and not DB rows: a single training set can be 10⁶+
rows. Storing them as model instances would bloat the DB and double the
storage cost (we already have the source rows). JSONL is the canonical
fine-tuning format anyway.

Each `kind` produces a different row schema:
  - question_generation:    {"prompt": ..., "completion": ...}
  - error_correction:       {"input": ..., "output": ...}
  - difficulty_estimation:  {"text": ..., "label": <float>}
  - cefr_classification:    {"text": ..., "label": "A1|...|C2"}
  - explanation_writing:    {"prompt": "Q + correct answer", "completion": explanation}
  - rag_corpus:             {"id": ..., "text": "Q + explanation", "metadata": {...}}
"""
from __future__ import annotations

import io
import json
import logging
import os
from datetime import datetime
from typing import Iterable

from django.conf import settings
from django.utils import timezone

from learning_core.models import AdaptiveExercise, UserError

from ..models import DatasetExportJob, TrainingDataset

logger = logging.getLogger(__name__)

DEFAULT_CHUNK = 1000


# ---------------------------------------------------------------------------
# Row builders — one per dataset kind. Yield dicts; caller serialises.
# ---------------------------------------------------------------------------

def _filter_qs(qs, filters: dict):
    f = filters or {}
    if f.get("cefr_level"):
        qs = qs.filter(cefr_level=f["cefr_level"])
    if f.get("question_type"):
        qs = qs.filter(question_type=f["question_type"])
    if f.get("generated_by"):
        qs = qs.filter(generated_by=f["generated_by"])
    if f.get("min_quality_score") is not None:
        qs = qs.filter(quality_score__gte=int(f["min_quality_score"]))
    if f.get("active_only", True):
        qs = qs.filter(is_active=True)
    if f.get("reviewed_only", False):
        qs = qs.filter(is_reviewed=True)
    return qs


def _question_generation_rows(filters: dict) -> Iterable[dict]:
    qs = _filter_qs(AdaptiveExercise.objects.all(), filters)
    for ex in qs.iterator(chunk_size=DEFAULT_CHUNK):
        prompt = (
            f"Generate a {ex.cefr_level or 'B1'} {ex.question_type} question"
            f" on the topic: {(ex.metadata or {}).get('topic') or 'general English'}."
        )
        completion = json.dumps({
            "question": ex.question,
            "options": ex.options or [],
            "correct_answer": ex.correct_answer,
            "explanation": ex.explanation,
        }, ensure_ascii=False)
        yield {"prompt": prompt, "completion": completion}


def _error_correction_rows(filters: dict) -> Iterable[dict]:
    qs = UserError.objects.exclude(original_text="").exclude(corrected_text="")
    if filters.get("min_severity"):
        qs = qs.filter(severity__gte=int(filters["min_severity"]))
    for err in qs.iterator(chunk_size=DEFAULT_CHUNK):
        yield {"input": err.original_text, "output": err.corrected_text,
               "error_type": err.error_type}


def _difficulty_estimation_rows(filters: dict) -> Iterable[dict]:
    qs = _filter_qs(AdaptiveExercise.objects.all(), filters)
    for ex in qs.iterator(chunk_size=DEFAULT_CHUNK):
        yield {"text": ex.question, "label": float(ex.difficulty_score)}


def _cefr_classification_rows(filters: dict) -> Iterable[dict]:
    qs = _filter_qs(AdaptiveExercise.objects.all(), filters).exclude(cefr_level="")
    for ex in qs.iterator(chunk_size=DEFAULT_CHUNK):
        yield {"text": ex.question, "label": ex.cefr_level}


def _explanation_writing_rows(filters: dict) -> Iterable[dict]:
    qs = _filter_qs(AdaptiveExercise.objects.all(), filters).exclude(explanation="")
    for ex in qs.iterator(chunk_size=DEFAULT_CHUNK):
        prompt = f"Question: {ex.question}\nCorrect answer: {ex.correct_answer}\nExplain why."
        yield {"prompt": prompt, "completion": ex.explanation}


def _rag_corpus_rows(filters: dict) -> Iterable[dict]:
    qs = _filter_qs(AdaptiveExercise.objects.all(), filters)
    for ex in qs.iterator(chunk_size=DEFAULT_CHUNK):
        text = ex.question
        if ex.explanation:
            text += "\n" + ex.explanation
        yield {
            "id": f"qb:{ex.id}",
            "text": text,
            "metadata": {
                "cefr_level": ex.cefr_level,
                "question_type": ex.question_type,
                "difficulty_score": ex.difficulty_score,
            },
        }


_BUILDERS = {
    "question_generation":    _question_generation_rows,
    "error_correction":       _error_correction_rows,
    "difficulty_estimation":  _difficulty_estimation_rows,
    "cefr_classification":    _cefr_classification_rows,
    "explanation_writing":    _explanation_writing_rows,
    "rag_corpus":             _rag_corpus_rows,
}


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

def _output_path(dataset: TrainingDataset, suffix: str = ".jsonl") -> str:
    base = getattr(settings, "FACTORY_DATASET_DIR", None)
    if not base:
        base = os.path.join(getattr(settings, "BASE_DIR", "."), "datasets")
    os.makedirs(base, exist_ok=True)
    ts = timezone.now().strftime("%Y%m%dT%H%M%S")
    return os.path.join(base, f"{dataset.name}-{ts}{suffix}")


def export(dataset: TrainingDataset, *, sink: io.IOBase | None = None,
           limit: int | None = None) -> DatasetExportJob:
    """Build the dataset and stream rows to `sink` (or a timestamped file).

    Always creates a `DatasetExportJob` row so re-runs and failures are
    auditable. Resumable across runs is *not* a goal here — just rerun
    the export; the source rows are stable."""
    job = DatasetExportJob.objects.create(dataset=dataset, status="running")
    builder = _BUILDERS.get(dataset.kind)
    if builder is None:
        job.status = "failed"
        job.error_message = f"Unknown dataset kind: {dataset.kind}"
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        return job

    own_sink = False
    if sink is None:
        path = _output_path(dataset)
        sink = open(path, "w", encoding="utf-8")
        own_sink = True
        job.file_path = path

    rows_written = 0
    bytes_written = 0
    try:
        for row in builder(dataset.filters or {}):
            line = json.dumps(row, ensure_ascii=False) + "\n"
            sink.write(line)
            rows_written += 1
            bytes_written += len(line.encode("utf-8"))
            if limit and rows_written >= limit:
                break
        job.status = "completed"
    except Exception as e:
        logger.exception("dataset export crashed: %s", e)
        job.status = "failed"
        job.error_message = str(e)[:500]
    finally:
        if own_sink:
            sink.close()
        job.row_count = rows_written
        job.bytes_written = bytes_written
        job.completed_at = timezone.now()
        job.save(update_fields=[
            "status", "row_count", "bytes_written", "completed_at",
            "file_path", "error_message",
        ])

    # Update dataset header.
    dataset.row_count = rows_written
    dataset.last_export_path = job.file_path
    dataset.last_exported_at = job.completed_at
    if dataset.status == "draft":
        dataset.status = "ready" if job.status == "completed" else "draft"
    dataset.save(update_fields=[
        "row_count", "last_export_path", "last_exported_at", "status", "updated_at",
    ])
    return job
