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
    "grammar accuracy, spelling, vocabulary range, sentence structure, clarity, "
    "task completion, fluency, and complexity. Return a JSON object via the "
    "assess_level tool. If the request includes dynamic items, include a "
    "question_scores row for every attempt_question_id. Do not invent "
    "pronunciation scores unless a real pronunciation scorer is provided."
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
                "grammar_score": {"type": "integer"},
                "vocabulary_score": {"type": "integer"},
                "fluency_score": {"type": "integer"},
                "overall_score": {"type": "integer"},
                "feedback": {"type": "string"},
                "question_scores": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "attempt_question_id": {"type": "integer"},
                            "score": {"type": "integer"},
                            "skill_score": {"type": "integer"},
                            "grammar_score": {"type": "integer"},
                            "vocabulary_score": {"type": "integer"},
                            "fluency_score": {"type": "integer"},
                            "feedback": {"type": "string"},
                            "error_analysis": {"type": "object"},
                        },
                        "required": ["attempt_question_id", "score", "feedback"],
                        "additionalProperties": True,
                    },
                },
            },
            "required": ["level", "written_score", "speaking_score", "feedback"],
            "additionalProperties": True,
        },
    },
}


def _build_user_prompt(answers: dict) -> str:
    if answers.get("mode") == "dynamic" and answers.get("items"):
        lines = [
            "Learner completed a dynamic CEFR placement test.",
            "Evaluate every item below using the question text, skill, topic, expected answer type, difficulty, and answer.",
            "Return question_scores with one row for every attempt_question_id.",
            "For written items evaluate grammar, spelling, vocabulary, sentence structure, clarity, and task completion.",
            "For speaking items evaluate transcript completeness, grammar from transcript, vocabulary, clarity, and transcript-based fluency.",
            "Do not return pronunciation_score unless a real pronunciation scorer is available.",
            "Aggregate final written_score, speaking_score, grammar_score, vocabulary_score, fluency_score, overall_score, and level from the item scores.",
            "",
        ]
        for item in answers.get("items", []):
            lines.append(
                f"{item.get('section', '').title()} #{item.get('order')}: "
                f"[{item.get('code')}] skill={item.get('skill')} "
                f"topic={item.get('topic')} type={item.get('expected_answer_type')} "
                f"difficulty={item.get('difficulty_score')}"
            )
            lines.append(f"Question: {item.get('question_text', '')}")
            if item.get("options"):
                lines.append(f"Options: {', '.join(map(str, item.get('options') or []))}")
            lines.append(f"Answer: {item.get('answer', '')}")
            lines.append("")
        return "\n".join(lines)

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
        # Centralised ai_usage wrapper (Prompt 12A.1): meters tokens/cost and
        # logs success/failure once. Function-calling passed via extra_payload.
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        data = ai_client.chat(
            payload["messages"], feature=AC.FEATURE_PLACEMENT_WRITTEN,
            role=AC.ROLE_STUDENT, model=settings.AI_MODEL,
            extra_payload={"tools": payload["tools"],
                           "tool_choice": payload["tool_choice"]},
            timeout=30,
        )
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
