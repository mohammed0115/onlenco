"""Quality checks for a rendered GeneratedQuestion dict.

Reuses the canonical 10-rule validator from `exams.services.question_quality`
(so item scores compare like-for-like across the platform), then layers
a few blueprint-specific checks on top.
"""
from __future__ import annotations

from typing import Tuple

from exams.services.question_quality import evaluate as base_evaluate


CRITICAL_FAILURES = {
    "missing_correct_answer",
    "correct_answer_not_in_options",
    "offensive",
    "invalid_cefr",
}


def evaluate(item: dict) -> Tuple[int, list[str]]:
    """Return (quality_score, [failed_check_codes]) for the rendered dict.

    Internally normalises field names (`question_text` ↔ `question`)
    so the shared validator works on either schema."""
    base_item = dict(item)
    if "question" not in base_item and base_item.get("question_text"):
        base_item["question"] = base_item["question_text"]
    return base_evaluate(base_item)


def passes(item: dict, *, threshold: int = 60,
           reject_critical: bool = True) -> bool:
    """Decide whether to accept the item.

    `reject_critical=True` (the default) means items with any critical
    failure are rejected even if their numeric score is above threshold —
    you do not want a question whose `correct_answer_not_in_options`
    sneaking through on the strength of an otherwise-fine score."""
    score, failures = evaluate(item)
    if reject_critical and any(f in CRITICAL_FAILURES for f in failures):
        return False
    return score >= threshold


def review_required(item: dict, *, ok_threshold: int = 80) -> bool:
    """Mark for human review when the item is borderline (passes basic
    checks but score is between 60 and 80)."""
    score, failures = evaluate(item)
    if any(f in CRITICAL_FAILURES for f in failures):
        return True
    return 60 <= score < ok_threshold


def annotate(item: dict) -> dict:
    """Stamp `quality_score`, `is_reviewed=False`, and `metadata.validation`
    onto the item; returns the same dict for chaining."""
    score, failures = evaluate(item)
    item["quality_score"] = score
    md = item.setdefault("metadata", {})
    md["validation"] = {"score": score, "failures": failures}
    if review_required(item):
        item["is_reviewed"] = False
        md["review_required"] = True
    else:
        item["is_reviewed"] = score >= 80
        md["review_required"] = False
    return item
