"""AI alternative-answer suggestions for ORAL placement questions.

The oral section is for guidance, NOT grading: after the student speaks
(answer captured as text via the realtime call's speech-to-text), we show a
few natural, beginner-friendly alternative answers under the label
"Other possible answers" / "إجابات أخرى مقترحة". These are never used to
score the student.

Cost control (Placement Phase 9):
  * The 5 fixed starter questions have built-in alternatives — zero AI cost.
  * Generated alternatives for custom oral questions are cached on the
    question (``PlacementQuestion.ai_alternatives``) so we never re-call.
  * The AI call goes through the ai_usage wrapper with
    feature="placement_alternatives" and NEVER enforces / consumes the
    student's paid AI-Tutor daily minutes.
"""
from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

# Built-in suggestions for the official starter questions (Phase 11) — keyed
# by question ``code`` so no AI call is ever made for the fixed bank.
#
# These are sentence FRAMES with a blank ("…"), not fixed names/countries
# (no "John" / "Egypt"), so the student learns the structure and fills in
# their own answer instead of being confused into copying a fixed value.
STARTER_ALTERNATIVES = {
    "sp.v2.001": ["My name is … .", "I'm … .", "… (your name)."],
    "sp.v2.002": ["I'm … years old.", "I am … .", "… years old."],
    "sp.v2.003": ["I'm from … .", "I come from … .", "I'm originally from … ."],
    "sp.v2.004": ["I'm a … .", "I work as a … .", "I'm a student."],
    "sp.v2.005": ["Because I need it for my job.", "To get a better job.",
                  "To study and travel."],
}

_PROMPT = (
    "Generate 3 to 5 natural, short, beginner-friendly alternative English "
    "answers for this placement interview question. The answers should be "
    "correct, simple, and suitable for A0/A1 learners. Do not grade the "
    "student. Return JSON only as {{\"alternatives\": [\"...\", \"...\"]}}.\n"
    "Question: {question}\n"
)


def alternatives_for(question, *, generate: bool = False,
                     student_transcript: str | None = None,
                     level_hint: str | None = None) -> list[str]:
    """Return alternative answers for an oral ``question``.

    Resolution order: cached on the question → built-in starter set → (only
    when ``generate=True``) a one-off AI call that is then cached. Returns an
    empty list on any failure, so the result page degrades gracefully.
    """
    cached = list(getattr(question, "ai_alternatives", None) or [])
    if cached:
        return cached
    starter = STARTER_ALTERNATIVES.get(getattr(question, "code", "") or "")
    if starter:
        return list(starter)
    if not generate:
        return []
    alts = _generate(question, student_transcript, level_hint)
    if alts:
        try:
            question.ai_alternatives = alts
            question.save(update_fields=["ai_alternatives"])
        except Exception:  # pragma: no cover - cache write must never break flow
            logger.warning("placement alternatives cache write failed", exc_info=True)
    return alts


def ensure_alternatives(question) -> list[str]:
    """Populate + cache alternatives for a question if missing (generate path)."""
    return alternatives_for(question, generate=True)


def _generate(question, transcript, level_hint) -> list[str]:
    try:
        from ai_usage import constants as C
        from ai_usage.services import ai_client

        prompt = _PROMPT.format(question=getattr(question, "question_text", "") or "")
        if level_hint:
            prompt += f"Learner level: {level_hint}\n"
        if transcript:
            prompt += f"Student said: {transcript}\n"

        text = ai_client.complete_text(
            prompt,
            # user=None → skips the student-approval gate; these suggestions
            # are question-level and cached, not per-student.
            user=None,
            role=C.ROLE_STUDENT,
            feature=C.FEATURE_PLACEMENT_ALTERNATIVES,
            enforce_minutes=False,   # NEVER touches AI-Tutor minutes
        )
        return _parse(text)
    except Exception:
        logger.warning("placement AI alternatives generation failed", exc_info=True)
        return []


def _parse(text: str) -> list[str]:
    """Best-effort JSON parse → a clean list of short answer strings."""
    if not text:
        return []
    raw = text.strip()
    # Strip ```json fences if the model wrapped the JSON.
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):] if "{" in raw else raw
    try:
        data = json.loads(raw)
    except Exception:
        return []
    items = data.get("alternatives") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        s = str(it).strip()
        if s and len(s) <= 120:
            out.append(s)
    return out[:5]
