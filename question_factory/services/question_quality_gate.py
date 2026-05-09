"""Strict question quality gate.

Single canonical entry point — every generated question must pass
through `evaluate()` (or `passes()`/`annotate()`) before it is stored,
shown to a student, or shipped to a training dataset.

Rule taxonomy
-------------
Twenty named rules (see `R_*` constants below) split into two tiers:

  * `CRITICAL_RULES` — failing one of these always rejects the item
    regardless of score. Examples: empty question, offensive content,
    answer not in MCQ options, exact duplicate.

  * Soft rules — each subtracts from the 100-point baseline. An item
    passes when the resulting score >= `threshold` (default 60). When
    the score is between `threshold` and `review_threshold` (default
    80), the gate flags it `review_required` so a human looks before
    the item goes live.

Public surface
--------------
    evaluate(item, *, threshold=60, review_threshold=80,
             check_db_duplicate=True) -> GateResult
    passes(item, **kwargs) -> bool
    annotate(item, **kwargs) -> dict      # mutates item.metadata in place
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from question_factory import constants as C

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule codes (the "20 validation rules" promised by the spec)
# ---------------------------------------------------------------------------

# Rule 1
R_EMPTY_QUESTION       = "empty_question"
# Rule 2
R_EMPTY_ANSWER         = "empty_answer"
# Rule 3
R_MCQ_OPTIONS_MIN      = "mcq_needs_4_options"
# Rule 4
R_ANSWER_NOT_IN_OPTS   = "answer_not_in_options"
# Rule 5
R_DUPLICATE_OPTIONS    = "duplicate_options"
# Rule 6
R_MISSING_EXPLANATION  = "missing_explanation"
# Rule 7
R_INVALID_CEFR         = "invalid_cefr"
# Rule 8
R_INVALID_SKILL        = "invalid_skill"
# Rule 9
R_DIFF_OUT_OF_RANGE    = "difficulty_out_of_range"
# Rule 10
R_PLACEHOLDER          = "unresolved_placeholder"
# Rule 11
R_BLANK_RUN            = "blank_run"
# Rule 12
R_TECH_TOKEN           = "technical_token"
# Rule 13
R_OFFENSIVE            = "offensive"
# Rule 14
R_PRIVATE_DATA         = "private_data"
# Rule 15
R_ANSWER_MISMATCH      = "answer_does_not_match"
# Rule 16
R_WRONG_LANGUAGE       = "wrong_language"
# Rule 17
R_LEVEL_DIFF_MISMATCH  = "level_difficulty_mismatch"
# Rule 18
R_EXACT_DUPLICATE      = "exact_duplicate"
# Rule 19 → quality_score is always computed; see GateResult.quality_score
# Rule 20 → review_required is always computed; see GateResult.review_required


CRITICAL_RULES = {
    R_EMPTY_QUESTION,
    R_EMPTY_ANSWER,
    R_MCQ_OPTIONS_MIN,    # an MCQ with <4 options is structurally broken
    R_ANSWER_NOT_IN_OPTS,
    R_DUPLICATE_OPTIONS,
    R_OFFENSIVE,
    R_INVALID_CEFR,
    R_PLACEHOLDER,
    R_BLANK_RUN,
    R_TECH_TOKEN,
    R_EXACT_DUPLICATE,
}


# Penalty weights — soft rules subtract from a 100-point baseline.
PENALTIES: dict[str, int] = {
    R_EMPTY_QUESTION:      100,
    R_EMPTY_ANSWER:        100,
    R_MCQ_OPTIONS_MIN:      25,
    R_ANSWER_NOT_IN_OPTS:   50,
    R_DUPLICATE_OPTIONS:    30,
    R_MISSING_EXPLANATION:  10,
    R_INVALID_CEFR:         30,
    R_INVALID_SKILL:        20,
    R_DIFF_OUT_OF_RANGE:    10,
    R_PLACEHOLDER:          30,
    R_BLANK_RUN:            30,
    R_TECH_TOKEN:            25,
    R_OFFENSIVE:           100,
    R_PRIVATE_DATA:         30,
    R_ANSWER_MISMATCH:      15,
    R_WRONG_LANGUAGE:       15,
    R_LEVEL_DIFF_MISMATCH:  10,
    R_EXACT_DUPLICATE:     100,
}


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

VALID_CEFR = {"A0", "A1", "A2", "B1", "B2", "C1", "C2"}
VALID_LANGS = {"en", "ar"}
VALID_SKILLS = {s for s, _ in C.SKILL_CHOICES}
EXPLANATION_REQUIRED_TYPES = {"multiple_choice", "fill_blank", "correction",
                              "vocabulary_matching", "grammar_transformation"}


# Difficulty bands per CEFR — slack ±0.10 applied at compare time.
DIFFICULTY_BANDS_BY_CEFR: dict[str, tuple[float, float]] = {
    "A0": (0.00, 0.30),
    "A1": (0.05, 0.40),
    "A2": (0.15, 0.55),
    "B1": (0.30, 0.70),
    "B2": (0.45, 0.85),
    "C1": (0.60, 0.95),
    "C2": (0.70, 1.00),
}


# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

# Rule 10: {{var}} or {% tag %} that survived the renderer
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]+\}\}|\{%[^{}]+%\}")

# Rule 11: "blank blank blank" / "null none undefined" runs
BLANK_RUN_RE = re.compile(
    r"\b(?:blank|null|none|undefined)(?:[\s\-_]+(?:blank|null|none|undefined)){1,}\b",
    re.IGNORECASE,
)

# Rule 12 — three patterns that should never reach a learner.
#   snake_case_word        → identifier-style with underscores BETWEEN letters
#   --option / word--word  → CLI flag / prose disguised as flag
#   __dunder__ / _x_       → underscore-flanked identifiers
# The fill-blank marker "___" alone is intentionally NOT matched by any of
# these — it is part of legitimate exercise prompts.
SNAKE_CASE_RE   = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z][a-z0-9]*)+\b")
DASH_FLAG_RE    = re.compile(r"(?:\b\w--+\w?|--+[A-Za-z])")
UNDERSCORE_ID_RE = re.compile(r"(?<![A-Za-z0-9])_+[A-Za-z][A-Za-z0-9_]*_+(?![A-Za-z0-9])")

# Rule 13
OFFENSIVE_RE = re.compile(r"\b(?:fuck|shit|bitch|asshole)\b", re.IGNORECASE)

# Rule 14
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
URL_RE   = re.compile(r"https?://\S+|www\.\S+")
PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[ \-.]?)?(?:\(\d{1,4}\)[ \-.]?)?"
    r"\d{3}[ \-.]?\d{3,4}[ \-.]?\d{2,4}(?!\d)"
)

# Rule 16
ARABIC_RE      = re.compile(r"[؀-ۿݐ-ݿ]")
NON_ASCII_RE   = re.compile(r"[^\x00-\x7F]+")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class GateResult:
    accepted: bool
    quality_score: int
    review_required: bool
    rejection_reason: str
    failed_rules: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "accepted": self.accepted,
            "quality_score": self.quality_score,
            "review_required": self.review_required,
            "rejection_reason": self.rejection_reason,
            "failed_rules": list(self.failed_rules),
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _content_hash_qf(question_text: str, correct_answer: str) -> str:
    """The hash format used by `question_factory.GeneratedQuestion.content_hash`."""
    from .duplicate_detector import hash_question
    return hash_question(question_text, correct_answer)


def _text_hash_lc(question_text: str, correct_answer: str) -> str:
    """The hash format used by `learning_core.AdaptiveExercise.text_hash`."""
    from exams.services.duplicate_detection import hash_text
    return hash_text(question_text + "|" + correct_answer)


def _check_db_duplicate(question_text: str, correct_answer: str) -> str | None:
    """Return the hash that matched if a duplicate exists, else None."""
    try:
        from learning_core.models import AdaptiveExercise
        from ..models import GeneratedQuestion
    except ImportError:  # pragma: no cover
        return None

    qf_hash = _content_hash_qf(question_text, correct_answer)
    if GeneratedQuestion.objects.filter(content_hash=qf_hash).exists():
        return f"qf:{qf_hash}"
    lc_hash = _text_hash_lc(question_text, correct_answer)
    if AdaptiveExercise.objects.filter(text_hash=lc_hash).exists():
        return f"lc:{lc_hash}"
    return None


def _flat_text(*parts: Any) -> str:
    """Concatenate string parts safely for combined-text checks."""
    out: list[str] = []
    for p in parts:
        if isinstance(p, str):
            out.append(p)
        elif isinstance(p, (list, tuple)):
            out.extend(str(x) for x in p)
        elif p is None:
            continue
        else:
            out.append(str(p))
    return " ".join(out)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(
    item: dict,
    *,
    threshold: int = 60,
    review_threshold: int = 80,
    check_db_duplicate: bool = True,
) -> GateResult:
    """Run all 20 rules. Returns a `GateResult`.

    The default thresholds:
      * `threshold=60` — score ≥ 60 → accepted (unless a critical rule
        failed).
      * `review_threshold=80` — score in [60, 80) → review_required.
    """
    failed: list[str] = []
    metadata: dict[str, Any] = {}

    q_text  = _normalise(item.get("question_text") or item.get("question") or "")
    correct = _normalise(item.get("correct_answer") or "")
    options = list(item.get("options") or [])
    qtype   = (item.get("question_type") or "").strip()
    cefr    = (item.get("cefr_level") or "").strip().upper()
    skill   = (item.get("skill") or "").strip()
    difficulty = item.get("difficulty_score")
    explanation = _normalise(item.get("explanation") or "")
    language = (item.get("language") or "en").strip().lower()

    # -- Rule 1: question text not empty -----------------------------
    if len(q_text) < 4:
        failed.append(R_EMPTY_QUESTION)

    # -- Rule 2: correct answer not empty ----------------------------
    if not correct:
        failed.append(R_EMPTY_ANSWER)

    # -- Rule 3, 4, 5: MCQ option checks -----------------------------
    if qtype == "multiple_choice":
        if len(options) < 4:
            failed.append(R_MCQ_OPTIONS_MIN)
        if correct and options and correct not in options:
            failed.append(R_ANSWER_NOT_IN_OPTS)
        if options:
            normalised = [str(o).strip().lower() for o in options]
            if len(set(normalised)) != len(normalised):
                failed.append(R_DUPLICATE_OPTIONS)

    # -- Rule 6: explanation exists for relevant types ---------------
    if not explanation and qtype in EXPLANATION_REQUIRED_TYPES:
        failed.append(R_MISSING_EXPLANATION)

    # -- Rule 7: CEFR valid ------------------------------------------
    if cefr and cefr not in VALID_CEFR:
        failed.append(R_INVALID_CEFR)

    # -- Rule 8: skill valid -----------------------------------------
    if skill and skill not in VALID_SKILLS:
        failed.append(R_INVALID_SKILL)

    # -- Rule 9: difficulty 0..1 -------------------------------------
    diff_value: float | None = None
    if difficulty is not None:
        try:
            diff_value = float(difficulty)
            if diff_value < 0.0 or diff_value > 1.0:
                failed.append(R_DIFF_OUT_OF_RANGE)
                diff_value = None
        except (TypeError, ValueError):
            failed.append(R_DIFF_OUT_OF_RANGE)
            diff_value = None

    # -- Rules 10-14, 16: text-content checks ------------------------
    flat = _flat_text(q_text, correct, explanation, options)

    # Rule 10: unresolved {{placeholder}}
    if PLACEHOLDER_RE.search(flat):
        failed.append(R_PLACEHOLDER)

    # Rule 11: "blank blank blank"
    if BLANK_RUN_RE.search(flat):
        failed.append(R_BLANK_RUN)

    # Rule 12: snake_case / -- / __dunder__
    if (SNAKE_CASE_RE.search(flat)
            or DASH_FLAG_RE.search(flat)
            or UNDERSCORE_ID_RE.search(flat)):
        failed.append(R_TECH_TOKEN)

    # Rule 13: offensive content
    if OFFENSIVE_RE.search(flat):
        failed.append(R_OFFENSIVE)

    # Rule 14: private data — flag rather than redact (callers can sanitise).
    if EMAIL_RE.search(flat) or URL_RE.search(flat) or PHONE_RE.search(flat):
        failed.append(R_PRIVATE_DATA)

    # -- Rule 15: answer matches the question ------------------------
    if correct:
        if correct.endswith("?") and not q_text.endswith("?"):
            failed.append(R_ANSWER_MISMATCH)
        elif q_text and len(correct) > max(200, len(q_text) * 5):
            # Implausibly long answer for the prompt size
            failed.append(R_ANSWER_MISMATCH)

    # -- Rule 16: language correct -----------------------------------
    if language not in VALID_LANGS:
        failed.append(R_WRONG_LANGUAGE)
    elif language == "en" and q_text:
        non_ascii_chars = sum(len(m) for m in NON_ASCII_RE.findall(q_text))
        # Allow some Unicode (e.g. smart quotes) but flag if dominant.
        if non_ascii_chars / max(1, len(q_text)) > 0.20:
            failed.append(R_WRONG_LANGUAGE)
    elif language == "ar" and q_text and not ARABIC_RE.search(q_text):
        failed.append(R_WRONG_LANGUAGE)

    # -- Rule 17: difficulty / CEFR alignment ------------------------
    if diff_value is not None and cefr in DIFFICULTY_BANDS_BY_CEFR:
        lo, hi = DIFFICULTY_BANDS_BY_CEFR[cefr]
        if diff_value < lo - 0.10 or diff_value > hi + 0.10:
            failed.append(R_LEVEL_DIFF_MISMATCH)

    # -- Rule 18: exact duplicate -----------------------------------
    if (check_db_duplicate
            and R_EMPTY_QUESTION not in failed
            and R_EMPTY_ANSWER not in failed):
        match = _check_db_duplicate(q_text, correct)
        if match:
            failed.append(R_EXACT_DUPLICATE)
            metadata["duplicate_match"] = match

    # -- Rule 19: quality_score (always computed) -------------------
    score = 100
    for r in failed:
        score -= PENALTIES.get(r, 5)
    score = max(0, min(100, score))

    # -- Rule 20: review_required (always computed) -----------------
    has_critical = any(r in CRITICAL_RULES for r in failed)
    accepted = (not has_critical) and score >= threshold
    review_required = (
        accepted and score < review_threshold
        # Soft fails alone trigger review even at high score.
        or (not has_critical and bool(failed) and score >= threshold)
    )

    rejection_reason = ""
    if not accepted:
        if has_critical:
            critical_failed = [r for r in failed if r in CRITICAL_RULES]
            rejection_reason = "critical:" + ",".join(critical_failed)
        elif failed:
            rejection_reason = "score_below_threshold:" + ",".join(failed[:3])
        else:
            rejection_reason = f"score_below_threshold:{score}<{threshold}"

    metadata["computed_hashes"] = {
        "qf": _content_hash_qf(q_text, correct) if q_text and correct else "",
    }

    return GateResult(
        accepted=accepted,
        quality_score=score,
        review_required=review_required,
        rejection_reason=rejection_reason,
        failed_rules=failed,
        metadata=metadata,
    )


def passes(item: dict, **kwargs) -> bool:
    """Convenience: True iff the gate accepts the item."""
    return evaluate(item, **kwargs).accepted


def annotate(item: dict, **kwargs) -> dict:
    """Stamp the gate result onto `item.metadata['quality_gate']` and
    set `quality_score` / `is_reviewed` fields. Returns the same dict
    for chaining."""
    result = evaluate(item, **kwargs)
    item["quality_score"] = result.quality_score
    md = item.setdefault("metadata", {})
    md["quality_gate"] = {
        "accepted":         result.accepted,
        "score":            result.quality_score,
        "review_required":  result.review_required,
        "rejection_reason": result.rejection_reason,
        "failed_rules":     list(result.failed_rules),
    }
    md.update({k: v for k, v in result.metadata.items() if k != "computed_hashes"})

    if result.accepted and not result.review_required:
        item["is_reviewed"] = True
    elif result.review_required:
        item["is_reviewed"] = False
    return item
