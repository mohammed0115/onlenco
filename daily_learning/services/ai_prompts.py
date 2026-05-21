"""AI prompt builder + response validator for daily-plan generation.

Used as the *last* fallback by daily_plan_generator — most plans are
satisfied by question-bank + templates and never reach this module.

The prompt forces JSON-only output and a strict schema. The validator
rejects malformed responses (no "underscore", "dash", JSON in
prose, raw keys, etc.) so partial/garbage AI content never lands in
the database.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Strings we never want to surface to the student.
_BANNED_SUBSTRINGS = (
    "underscore", "blank blank blank", "____ ____ ____",
    "item_type", "correct_answer", "difficulty_score", "{",
    "[null", "TODO", "lorem ipsum",
)


def build_prompt(
    *,
    cefr_level: str,
    language: str,
    weaknesses: list[dict] | None,
    mistakes: list[dict] | None,
    onboarding_path: str,
    estimated_minutes: int,
    plan_type: str,
) -> str:
    """Return the user-side prompt body. The provider wraps it with a
    system-level "respond with JSON only" instruction."""
    weak_str = "; ".join(
        (w.get("grammar_topic_name") or w.get("skill_name") or "—")
        for w in (weaknesses or [])[:3]
    ) or "none"
    mist_str = "; ".join(
        (m.get("corrected_text") or "")[:60]
        for m in (mistakes or [])[:3]
    ) or "none"
    return f"""Generate a daily English learning plan for one student.

Student context:
- CEFR level: {cefr_level}
- Preferred language: {language}
- Weaknesses: {weak_str}
- Recent corrections: {mist_str}
- Onboarding path: {onboarding_path}
- Plan type: {plan_type}
- Estimated time (minutes): {estimated_minutes}

Requirements:
- Output between 5 and 8 short tasks.
- Match the student's level: A0 = very simple; B1+ = more complex.
- Include at least one vocabulary item, one quiz, one speaking task, and one motivation line.
- Use Arabic for explanations when language is "ar"; English otherwise.
- Never use raw technical keys, JSON markers, or words like
  "underscore", "dash", "blank blank blank" in any student-facing text.
- For A0, teach by example only: one word, picture or sound cue, one short sentence,
  speaking practice, then one simple question. Do not show classroom labels like
  "verb", "tense", or "pronoun" to the student.
- Keep each instruction under 200 characters.

Return JSON only, with this exact shape (no prose, no markdown):
{{
  "title": "...",
  "description": "...",
  "items": [
    {{
      "item_type": "vocabulary|grammar_tip|reading|listening|speaking|writing|quiz|review_mistake|ai_tutor_practice",
      "title": "...",
      "instructions": "...",
      "content_text": "...",
      "question": "...",
      "options": [],
      "correct_answer": "...",
      "explanation": "...",
      "skill": "vocabulary|grammar|reading|listening|speaking|writing|pronunciation|mixed",
      "difficulty_score": 0.0
    }}
  ],
  "motivation_message": "..."
}}
"""


def validate_ai_output(raw: Any) -> dict | None:
    """Return a cleaned plan dict, or None if the AI output is unusable.

    Accepts either a dict (already parsed) or a JSON string.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except Exception:
            # Try to recover JSON embedded inside prose.
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                return None
            try:
                data = json.loads(m.group(0))
            except Exception:
                return None
    elif isinstance(raw, dict):
        data = raw
    else:
        return None

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    motivation = (data.get("motivation_message") or "").strip()
    raw_items = data.get("items") or []
    if not isinstance(raw_items, list) or not (5 <= len(raw_items) <= 8):
        return None

    cleaned: list[dict] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            return None
        item = _clean_item(raw_item)
        if item is None:
            return None
        cleaned.append(item)

    if not title or not motivation:
        return None
    if _contains_banned(title) or _contains_banned(motivation):
        return None

    return {
        "title": title[:200],
        "description": description[:1000],
        "items": cleaned,
        "motivation_message": motivation[:500],
    }


# ----- private helpers ------------------------------------------------

_ALLOWED_ITEM_TYPES = {
    "vocabulary", "grammar_tip", "reading", "listening", "speaking",
    "writing", "quiz", "review_mistake", "ai_tutor_practice", "motivation",
}
_ALLOWED_SKILLS = {
    "vocabulary", "grammar", "reading", "listening", "speaking",
    "writing", "pronunciation", "mixed",
}


def _clean_item(d: dict) -> dict | None:
    item_type = (d.get("item_type") or "").strip()
    if item_type not in _ALLOWED_ITEM_TYPES:
        return None
    skill = (d.get("skill") or "mixed").strip()
    if skill not in _ALLOWED_SKILLS:
        skill = "mixed"
    title = (d.get("title") or "").strip()
    instructions = (d.get("instructions") or "").strip()
    if not title or not instructions:
        return None
    if any(_contains_banned(s) for s in (title, instructions,
                                          d.get("content_text") or "",
                                          d.get("question") or "")):
        return None
    options = d.get("options") or []
    if not isinstance(options, list):
        options = []
    options = [str(o).strip() for o in options if str(o).strip()]
    try:
        difficulty = float(d.get("difficulty_score") or 0.3)
    except Exception:
        difficulty = 0.3
    difficulty = max(0.0, min(1.0, difficulty))
    return {
        "item_type": item_type,
        "title": title[:200],
        "instructions": instructions[:500],
        "content_text": (d.get("content_text") or "")[:2000],
        "question": (d.get("question") or "")[:500],
        "options": options,
        "correct_answer": (d.get("correct_answer") or "")[:300],
        "explanation": (d.get("explanation") or "")[:500],
        "skill": skill,
        "difficulty_score": difficulty,
        "estimated_minutes": 2,
    }


def _contains_banned(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(b in low for b in _BANNED_SUBSTRINGS)
