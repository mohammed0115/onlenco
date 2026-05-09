"""Quality router — escalates from cheap rules to expensive AI only when
necessary, so 99 %+ of validations cost zero tokens.

Decision tree:
  1. Run rule-based check (cheap, deterministic, ~µs/item).
  2. If the score is high (>=80) and no critical failure: APPROVE.
  3. If the score is very low (<40) and a critical failure: REJECT.
  4. Otherwise: escalate to the LLM router as a "validator only" call —
     OpenAI is the *fallback* model here, not the default.

This file does NOT generate questions. It validates them. Generation is
in `template_engine` (cheap) and `ai_question_generator` (already in
exams/services/).
"""
from __future__ import annotations

import json
import logging
from typing import Tuple

from exams.services.question_quality import evaluate as rule_evaluate
from . import llm_router

logger = logging.getLogger(__name__)

CRITICAL_FAILURES = {
    "missing_correct_answer",
    "correct_answer_not_in_options",
    "offensive",
    "invalid_cefr",
}

DECISION_APPROVE   = "approve"
DECISION_ESCALATE  = "escalate"
DECISION_REJECT    = "reject"


def _rule_decision(score: int, failures: list[str]) -> str:
    if any(f in CRITICAL_FAILURES for f in failures):
        return DECISION_REJECT if score < 40 else DECISION_ESCALATE
    if score >= 80:
        return DECISION_APPROVE
    if score < 40:
        return DECISION_REJECT
    return DECISION_ESCALATE


def _ai_validate(item: dict) -> dict | None:
    """Ask the LLM router to validate a single item. Returns a dict like
    `{"approve": bool, "reason": "...", "fixes": ["..."]}` or None on
    network/parse failure (caller falls back to rule decision)."""
    sys = (
        "You are a strict CEFR-aware ESL question validator. "
        "Reply with strict JSON only."
    )
    user = (
        "Validate this learning item. Reply JSON: "
        '{"approve": true|false, "reason": "...", "fixes": ["..."]}.\n\n'
        + json.dumps({
            "question": item.get("question") or item.get("question_text"),
            "options": item.get("options"),
            "correct_answer": item.get("correct_answer"),
            "cefr_level": item.get("cefr_level"),
            "skill": item.get("skill") or item.get("topic_kind"),
        }, ensure_ascii=False)
    )
    payload = llm_router.chat(
        [{"role": "system", "content": sys}, {"role": "user", "content": user}],
        json_mode=True,
    )
    return llm_router.parse_json_content(payload)


def validate(item: dict, *, allow_ai: bool = True,
             ai_threshold_low: int = 40, ai_threshold_high: int = 80) -> Tuple[bool, dict]:
    """Returns (approved, report).

    `report` always contains the rule score + failures, plus an `ai`
    section when escalation occurred. Callers persist the report into
    `metadata["quality_report"]` for later auditing."""
    score, failures = rule_evaluate(item)
    decision = _rule_decision(score, failures)
    report = {
        "rule_score": score, "rule_failures": failures, "decision": decision,
    }
    if decision == DECISION_APPROVE:
        return True, report
    if decision == DECISION_REJECT:
        return False, report
    if not allow_ai:
        # No AI permitted → conservative fallback. Critical failures must
        # never sneak through on score alone, even if other rules passed.
        has_critical = any(f in CRITICAL_FAILURES for f in failures)
        approved = score >= 60 and not has_critical
        report["decision"] = "approve" if approved else "reject"
        report["forced_no_ai"] = True
        return approved, report
    # Escalate to AI.
    ai = _ai_validate(item)
    if ai is None:
        report["ai"] = {"unavailable": True}
        # Conservative fallback: approve only if the rule score is decent.
        return score >= ai_threshold_high, report
    approved = bool(ai.get("approve"))
    report["ai"] = ai
    report["decision"] = "approve" if approved else "reject"
    return approved, report
