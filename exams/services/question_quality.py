"""Quality validator. Returns a 0..100 score + list of failed checks.

Calls are cheap — pure-Python, no DB, no AI. Used both during generation
(reject below threshold) and as a periodic batch validator (flag for
review)."""
from __future__ import annotations

import re
from typing import Tuple

from accounts.models import CEFR_CHOICES

_VALID_CEFR = {c[0] for c in CEFR_CHOICES}
_PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}|\{%[^{}]+%\}")
_BLANK_RUN_RE = re.compile(r"\b(?:blank|null|none|undefined)(?:[\s\-_]+(?:blank|null|none|undefined))+\b", re.IGNORECASE)
_TECH_TOKENS_RE = re.compile(r"\b(?:underscore|dash dash|tilde tilde)\b", re.IGNORECASE)
_OFFENSIVE_RE = re.compile(r"\b(?:fuck|shit|bitch|asshole)\b", re.IGNORECASE)
_MIN_QUESTION_LEN = 4


def evaluate(item: dict) -> Tuple[int, list[str]]:
    """Return `(quality_score, [failed_check_codes])`.

    Quality score starts at 100, each failed check subtracts a penalty
    (10–30). Score is clamped to [0, 100]."""
    failures: list[str] = []
    score = 100

    q = (item.get("question") or item.get("question_text") or "").strip()
    if len(q) < _MIN_QUESTION_LEN:
        failures.append("question_too_short")
        score -= 30

    correct = (item.get("correct_answer") or "").strip()
    if not correct:
        failures.append("missing_correct_answer")
        score -= 30

    qtype = item.get("question_type") or ""
    options = item.get("options") or []

    if qtype == "multiple_choice":
        if len(options) < 4:
            failures.append("mcq_needs_4_options")
            score -= 20
        if correct and options and correct not in options:
            failures.append("correct_answer_not_in_options")
            score -= 25

    diff = item.get("difficulty_score")
    try:
        diff = float(diff)
        if diff < 0 or diff > 1:
            failures.append("difficulty_out_of_range")
            score -= 10
    except (TypeError, ValueError):
        failures.append("difficulty_not_numeric")
        score -= 10

    cefr = (item.get("cefr_level") or "").strip()
    if cefr and cefr not in _VALID_CEFR:
        failures.append("invalid_cefr")
        score -= 20

    if not (item.get("skill_id") or item.get("skill") or item.get("metadata", {}).get("skill")):
        # skill is optional but flagged
        pass

    if _PLACEHOLDER_RE.search(q):
        failures.append("unresolved_placeholder")
        score -= 15
    if _BLANK_RUN_RE.search(q):
        failures.append("blank_run")
        score -= 15
    if _TECH_TOKENS_RE.search(q):
        failures.append("technical_token")
        score -= 10
    if _OFFENSIVE_RE.search(q) or _OFFENSIVE_RE.search(correct):
        failures.append("offensive")
        score -= 50

    lang = item.get("language") or "en"
    if lang not in ("en", "ar"):
        failures.append("invalid_language")
        score -= 10

    score = max(0, min(100, score))
    return score, failures


def passes(item: dict, threshold: int = 60) -> bool:
    score, _ = evaluate(item)
    return score >= threshold
