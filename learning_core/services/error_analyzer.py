"""Error Analysis Engine.

Public entry point: analyze_text(user, text, source_type="writing", context=None).

If `AI_API_KEY` is configured, call an OpenAI-compatible chat-completions
endpoint with a tool/function call enforcing JSON schema. Otherwise (or on
any failure), fall back to a deterministic heuristic analyzer. Either way
the user flow never crashes: callers receive a dict with the same shape and
UserError rows are persisted.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests
from django.conf import settings
from django.db import transaction

from learning_core.models import (
    ERROR_SOURCE_CHOICES,
    ERROR_TYPE_CHOICES,
    SKILL_CATEGORY_CHOICES,
    GrammarTopic,
    Skill,
    UserError,
)

from .prompts import (
    ERROR_ANALYSIS_SYSTEM,
    ERROR_ANALYSIS_TOOL,
    build_error_analysis_user_prompt,
)

logger = logging.getLogger(__name__)

ALLOWED_ERROR_TYPES = {choice[0] for choice in ERROR_TYPE_CHOICES}
ALLOWED_SKILL_CATEGORIES = {choice[0] for choice in SKILL_CATEGORY_CHOICES}
ALLOWED_SOURCES = {choice[0] for choice in ERROR_SOURCE_CHOICES}


def analyze_text(
    user, text: str, source_type: str = "writing", context: dict | None = None
) -> dict:
    """Run error analysis. Always returns a dict, never raises to caller."""
    if source_type not in ALLOWED_SOURCES:
        source_type = "writing"

    text = (text or "").strip()
    if not text:
        return _empty_result()

    # Rate limit: if user is over their daily AI quota, skip the AI call
    # and use the heuristic fallback. Never blocks the flow.
    use_ai = bool(settings.AI_API_KEY)
    if use_ai and user is not None and getattr(user, "is_authenticated", False):
        try:
            from core.services.ai_usage import is_within_limit
            if not is_within_limit(user, "error_analysis"):
                use_ai = False
                logger.info("Error analyzer: user over daily AI limit, falling back.")
        except Exception:
            pass

    raw = _call_ai(text, context) if use_ai else None
    if raw is None:
        result = _heuristic_analyze(text)
    else:
        result = _validate_ai_result(raw, text)
        if result is None:
            logger.warning("Error analyzer: AI response invalid, falling back.")
            result = _heuristic_analyze(text)

    if user is not None and getattr(user, "is_authenticated", True):
        _persist_errors(user, result, source_type)

    return result


def _empty_result() -> dict:
    return {"original_text": "", "corrected_text": "", "errors": []}


def _call_ai(text: str, context: dict | None) -> dict | None:
    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": ERROR_ANALYSIS_SYSTEM},
            {
                "role": "user",
                "content": build_error_analysis_user_prompt(text, context),
            },
        ],
        "tools": [ERROR_ANALYSIS_TOOL],
        "tool_choice": {
            "type": "function",
            "function": {"name": "report_errors"},
        },
    }
    try:
        resp = requests.post(
            f"{settings.AI_API_BASE.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        tool_call = data["choices"][0]["message"]["tool_calls"][0]
        result = json.loads(tool_call["function"]["arguments"])
        try:
            from core.services.ai_usage import log_usage
            usage = data.get("usage", {}) or {}
            log_usage(
                None,
                "error_analysis",
                model=settings.AI_MODEL,
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                success=True,
            )
        except Exception:
            pass
        return result
    except Exception as e:
        logger.warning("Error analyzer AI call failed: %s", e)
        try:
            from core.services.ai_usage import log_usage
            log_usage(None, "error_analysis", model=settings.AI_MODEL, success=False, error_message=str(e))
        except Exception:
            pass
        return None


def _validate_ai_result(raw: Any, original_text: str) -> dict | None:
    if not isinstance(raw, dict):
        return None
    errors = raw.get("errors")
    if not isinstance(errors, list):
        return None

    cleaned_errors: list[dict] = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        et = item.get("error_type")
        if et not in ALLOWED_ERROR_TYPES:
            continue
        sev = item.get("severity")
        if not isinstance(sev, int) or sev < 1 or sev > 10:
            continue
        conf = item.get("confidence", 0.0)
        try:
            conf = float(conf)
        except (TypeError, ValueError):
            conf = 0.0
        conf = max(0.0, min(1.0, conf))
        sk_cat = item.get("skill_category")
        if sk_cat is not None and sk_cat not in ALLOWED_SKILL_CATEGORIES:
            sk_cat = None
        cleaned_errors.append(
            {
                "error_type": et,
                "original_fragment": str(item.get("original_fragment", ""))[:500],
                "corrected_fragment": str(item.get("corrected_fragment", ""))[:500],
                "grammar_topic": str(item.get("grammar_topic", "") or "").strip(),
                "skill_category": sk_cat,
                "severity": sev,
                "explanation": str(item.get("explanation", ""))[:1000],
                "confidence": conf,
            }
        )

    return {
        "original_text": str(raw.get("original_text") or original_text)[:5000],
        "corrected_text": str(raw.get("corrected_text") or original_text)[:5000],
        "errors": cleaned_errors,
    }


_HEURISTIC_RULES = [
    # Subject-verb agreement (very crude)
    (
        re.compile(r"\b(I|you|we|they)\s+(goes|has|does|was)\b", re.IGNORECASE),
        {
            "error_type": "grammar",
            "skill_category": "grammar",
            "grammar_topic": "Subject-verb agreement",
            "explanation": "Subject pronoun does not agree with the verb form.",
            "severity": 6,
        },
    ),
    (
        re.compile(r"\b(he|she|it)\s+(go|have|do|were)\b(?!\s+been)", re.IGNORECASE),
        {
            "error_type": "grammar",
            "skill_category": "grammar",
            "grammar_topic": "Subject-verb agreement",
            "explanation": "Third-person singular requires -s/-es on the verb.",
            "severity": 6,
        },
    ),
    # Common typos
    (
        re.compile(r"\bteh\b", re.IGNORECASE),
        {
            "error_type": "spelling",
            "skill_category": "vocabulary",
            "grammar_topic": "Spelling",
            "explanation": "'teh' should be 'the'.",
            "severity": 2,
        },
    ),
    (
        re.compile(r"\brecieve\b", re.IGNORECASE),
        {
            "error_type": "spelling",
            "skill_category": "vocabulary",
            "grammar_topic": "Spelling",
            "explanation": "'recieve' should be 'receive' (i before e).",
            "severity": 2,
        },
    ),
    # Missing space after comma/period
    (
        re.compile(r"[a-z],[a-z]", re.IGNORECASE),
        {
            "error_type": "punctuation",
            "skill_category": "writing",
            "grammar_topic": "Punctuation",
            "explanation": "Missing space after a comma.",
            "severity": 3,
        },
    ),
]


def _heuristic_analyze(text: str) -> dict:
    """Deterministic regex-based fallback. Returns the same shape as AI."""
    errors: list[dict] = []
    seen_fragments: set[str] = set()

    for pattern, template in _HEURISTIC_RULES:
        for match in pattern.finditer(text):
            fragment = match.group(0)
            key = (template["error_type"], fragment.lower())
            if key in seen_fragments:
                continue
            seen_fragments.add(key)
            errors.append(
                {
                    "error_type": template["error_type"],
                    "original_fragment": fragment,
                    "corrected_fragment": "",
                    "grammar_topic": template["grammar_topic"],
                    "skill_category": template["skill_category"],
                    "severity": template["severity"],
                    "explanation": template["explanation"],
                    "confidence": 0.4,
                }
            )

    # Capitalization at sentence start
    if text and text[0].islower():
        errors.append(
            {
                "error_type": "punctuation",
                "original_fragment": text.split(" ", 1)[0],
                "corrected_fragment": text.split(" ", 1)[0].capitalize(),
                "grammar_topic": "Capitalization",
                "skill_category": "writing",
                "severity": 2,
                "explanation": "Sentences should start with a capital letter.",
                "confidence": 0.5,
            }
        )

    return {
        "original_text": text,
        "corrected_text": text,  # heuristic doesn't rewrite the whole text
        "errors": errors,
    }


def _resolve_skill(skill_category: str | None) -> Skill | None:
    if not skill_category:
        return None
    return Skill.objects.filter(category=skill_category, is_active=True).first()


def _resolve_topic(name: str | None) -> GrammarTopic | None:
    if not name:
        return None
    name = name.strip()
    if not name:
        return None
    return (
        GrammarTopic.objects.filter(name__iexact=name).first()
        or GrammarTopic.objects.filter(slug__iexact=name.lower().replace(" ", "-")).first()
    )


def _persist_errors(user, result: dict, source_type: str) -> None:
    errors = result.get("errors") or []
    if not errors:
        return
    rows = []
    for err in errors:
        rows.append(
            UserError(
                user=user,
                source_type=source_type,
                original_text=err.get("original_fragment", ""),
                corrected_text=err.get("corrected_fragment", ""),
                error_type=err["error_type"],
                grammar_topic=_resolve_topic(err.get("grammar_topic")),
                skill=_resolve_skill(err.get("skill_category")),
                severity=err["severity"],
                explanation=err.get("explanation", ""),
                ai_confidence=err.get("confidence", 0.0),
                metadata={
                    "skill_category": err.get("skill_category"),
                    "grammar_topic_name": err.get("grammar_topic"),
                },
            )
        )
    with transaction.atomic():
        UserError.objects.bulk_create(rows)
