"""
AI placement assessor.

This module wraps the LLM call. In production it speaks to any
OpenAI-compatible chat-completions endpoint (OpenAI, Groq, Together,
Lovable, etc.). When `AI_API_KEY` is empty we fall back to a simple
deterministic heuristic so the app stays usable in development and
during local demos.
"""
from __future__ import annotations

import json
import logging
import re

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are an expert English language assessor using the CEFR framework "
    "(A0, A1, A2, B1, B2, C1, C2). Evaluate the learner's responses across "
    "grammar accuracy, vocabulary range, fluency, and complexity. Return a "
    "JSON object via the assess_level tool with: level (CEFR), written_score "
    "(0-100), speaking_score (0-100), feedback (2-3 sentences, encouraging, "
    "in English)."
)

ASSESS_TOOL = {
    "type": "function",
    "function": {
        "name": "assess_level",
        "description": "Return CEFR assessment.",
        "parameters": {
            "type": "object",
            "properties": {
                "level": {"type": "string",
                          "enum": ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]},
                "written_score": {"type": "integer"},
                "speaking_score": {"type": "integer"},
                "feedback": {"type": "string"},
            },
            "required": ["level", "written_score", "speaking_score", "feedback"],
            "additionalProperties": False,
        },
    },
}


def _build_user_prompt(answers: dict) -> str:
    return (
        "Learner answers:\n"
        f"1. Grammar MCQ ('She ___ to school every day'): {answers.get('q1','')}\n"
        f"2. Grammar MCQ (which is correct): {answers.get('q2','')}\n"
        f"3. Free writing about hobbies: {answers.get('q3','')}\n"
        f"4. Past tense description (yesterday): {answers.get('q4','')}\n"
        "5. Spoken response transcript (talked for ~45 seconds about their daily routine): "
        f"{answers.get('q5','')}\n\n"
        "Use answers 1-4 to score 'written_score' and answer 5 to score "
        "'speaking_score'. Each is 0-100. Return CEFR level and short feedback."
    )


def _heuristic_fallback(answers: dict) -> dict:
    """Crude rule-based scorer used when no API key is configured.

    Looks at MCQ correctness, sentence count, and word variety. It's not
    a substitute for a real LLM, but it's enough to keep the demo flow
    end-to-end testable.
    """
    score = 0

    if answers.get("q1") == "goes":
        score += 20
    if answers.get("q2") == "If I had known, I would have helped.":
        score += 25

    q3 = (answers.get("q3") or "").strip()
    q4 = (answers.get("q4") or "").strip()
    q5 = (answers.get("q5") or "").strip()

    q3_words = re.findall(r"[A-Za-z']+", q3)
    q4_words = re.findall(r"[A-Za-z']+", q4)
    q4_sentences = [s for s in re.split(r"[.!?]+", q4) if s.strip()]

    # Reward writing length and lexical variety
    score += min(len(q3_words) // 2, 15)
    score += min(len(q4_words) // 4, 20)
    score += min(len(q4_sentences) * 3, 15)
    unique_ratio = (len(set(w.lower() for w in q4_words)) / len(q4_words)) if q4_words else 0
    score += int(unique_ratio * 10)

    score = max(0, min(score, 100))

    q5_words = re.findall(r"[A-Za-z']+", q5)
    q5_sentences = [s for s in re.split(r"[.!?]+", q5) if s.strip()]
    speaking = 0
    speaking += min(len(q5_words) // 3, 35)
    speaking += min(len(q5_sentences) * 5, 30)
    unique_ratio_5 = (len(set(w.lower() for w in q5_words)) / len(q5_words)) if q5_words else 0
    speaking += int(unique_ratio_5 * 25)
    speaking = max(0, min(speaking, 100))

    if score < 15:
        level = "A0"
    elif score < 30:
        level = "A1"
    elif score < 45:
        level = "A2"
    elif score < 60:
        level = "B1"
    elif score < 75:
        level = "B2"
    elif score < 90:
        level = "C1"
    else:
        level = "C2"

    return {
        "level": level,
        "written_score": score,
        "speaking_score": speaking,
        "feedback": (
            "Nice work completing the assessment! Keep practising daily reading "
            "and speaking — focus on tense accuracy and vocabulary range. "
            "(Heuristic fallback used; configure AI_API_KEY for AI grading.)"
        ),
    }


def assess(answers: dict) -> dict:
    """Run the assessment. Returns a dict with `level`, `written_score`,
    `speaking_score`, and `feedback`."""

    if not settings.AI_API_KEY:
        logger.warning("AI_API_KEY not set; using heuristic fallback.")
        return _heuristic_fallback(answers)

    payload = {
        "model": settings.AI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(answers)},
        ],
        "tools": [ASSESS_TOOL],
        "tool_choice": {"type": "function", "function": {"name": "assess_level"}},
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
        # Sanity-check the keys we care about
        for k in ("level", "written_score", "speaking_score", "feedback"):
            if k not in result:
                raise ValueError(f"missing key {k} in AI response")
        return result
    except Exception as e:
        logger.exception("AI placement call failed: %s", e)
        # Fall back rather than 500ing — better UX
        result = _heuristic_fallback(answers)
        result["feedback"] = (
            result["feedback"]
            + " (Note: live AI scoring temporarily unavailable.)"
        )
        return result
