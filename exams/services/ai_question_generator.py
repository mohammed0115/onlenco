"""Optional AI question generator. Falls back gracefully when no API key.

Yields the same dict shape as `template_question_generator.generate()`
so the bulk pipeline can mix outputs freely. Marks every item with
`generated_by="ai"` and stamps `is_reviewed=False` so a human can audit
before exposing to learners.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import requests
from django.conf import settings

from .duplicate_detection import hash_text
from .question_quality import evaluate as evaluate_quality

logger = logging.getLogger(__name__)


_SCHEMA_HINT = """\
Reply with strict JSON: {"questions": [...]}.
Each question object has:
  question_text, instructions, options (array of strings),
  correct_answer, acceptable_answers (array), explanation,
  feedback_correct, feedback_wrong, difficulty_score (0..1),
  cefr_level (A0/A1/A2/B1/B2/C1/C2),
  skill (grammar/vocabulary/reading/listening/writing/speaking),
  question_type (multiple_choice/fill_blank/short_answer/...),
  grammar_topic (string).
"""


def _build_messages(*, cefr_level, skill, count, question_type, grammar_topic, language):
    sys = (
        "You generate English-learning exam questions for the Onlenco "
        "platform. Match the CEFR level exactly. Avoid duplicates. Avoid "
        "raw technical tokens (snake_case, blank blank, JSON, URLs). "
        "Avoid offensive content. Output only valid JSON."
    )
    user = (
        f"Generate {count} questions.\n"
        f"CEFR level: {cefr_level}\n"
        f"Skill: {skill}\n"
        f"Question type: {question_type}\n"
        f"Grammar topic: {grammar_topic}\n"
        f"Language of instruction: {language}\n\n"
        + _SCHEMA_HINT
    )
    return [
        {"role": "system", "content": sys},
        {"role": "user", "content": user},
    ]


def _call_llm(messages: list[dict]) -> Optional[dict]:
    if not settings.AI_API_KEY:
        return None
    try:
        # Centralised ai_usage wrapper (Prompt 12A.1): content generation,
        # role=system (admin/teacher-triggered, not student minutes).
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        return ai_client.chat(
            messages, feature=AC.FEATURE_CONTENT_GENERATION, role=AC.ROLE_SYSTEM,
            model=settings.AI_MODEL,
            extra_payload={"max_tokens": 1500, "temperature": 0.5,
                           "response_format": {"type": "json_object"}},
            timeout=60,
        )
    except Exception as e:
        logger.warning("ai_question_generator: LLM call failed: %s", e)
        return None


def _parse(payload: dict) -> list[dict]:
    if not payload:
        return []
    try:
        text = payload["choices"][0]["message"].get("content") or ""
        data = json.loads(text)
        questions = data.get("questions") or []
    except Exception as e:
        logger.warning("ai_question_generator: parse failed: %s", e)
        return []
    return [q for q in questions if isinstance(q, dict)]


def _to_bank_dict(raw: dict, *, code: str, cefr_level: str, skill: str) -> Optional[dict]:
    """Convert one LLM-emitted item to the AdaptiveExercise dict shape."""
    q_text = (raw.get("question_text") or "").strip()
    correct = (raw.get("correct_answer") or "").strip()
    if not q_text or not correct:
        return None
    options = list(raw.get("options") or [])
    qtype = raw.get("question_type") or "multiple_choice"
    text_hash = hash_text(q_text + "|" + correct)
    item = {
        "code": code,
        "skill_id": None,
        "topic_id": None,
        "cefr_level": raw.get("cefr_level") or cefr_level,
        "difficulty_score": float(raw.get("difficulty_score") or 0.5),
        "question_type": qtype,
        "question": q_text,
        "options": options,
        "correct_answer": correct,
        "explanation": raw.get("explanation") or "",
        "feedback_correct": raw.get("feedback_correct") or "",
        "feedback_wrong": raw.get("feedback_wrong") or "",
        "estimated_time_seconds": 35,
        "points": 1,
        "language": "en",
        "generated_by": "ai",
        "generated_by_ai": True,
        "is_active": True,
        "is_reviewed": False,
        "acceptable_answers": list(raw.get("acceptable_answers") or [correct]),
        "text_hash": text_hash,
        "metadata": {
            "topic": raw.get("grammar_topic") or "",
            "bank_code": code,
            "generator": "ai",
        },
    }
    score, _ = evaluate_quality(item)
    item["quality_score"] = score
    return item


def generate(
    *,
    cefr_level: str,
    skill: str,
    count: int = 5,
    question_type: str = "multiple_choice",
    grammar_topic: str = "",
    language: str = "en",
    code_prefix: str = "ai",
) -> list[dict]:
    """Returns up to `count` AI-generated items. Empty list on any failure
    (caller falls back to templates)."""
    messages = _build_messages(
        cefr_level=cefr_level, skill=skill, count=count,
        question_type=question_type, grammar_topic=grammar_topic,
        language=language,
    )
    data = _call_llm(messages)
    raw = _parse(data)
    if not raw:
        return []
    out: list[dict] = []
    for i, item in enumerate(raw):
        code = f"{code_prefix}:{cefr_level}:{skill}:{question_type}:{i:04d}"
        d = _to_bank_dict(item, code=code, cefr_level=cefr_level, skill=skill)
        if d is None:
            continue
        out.append(d)
    return out
