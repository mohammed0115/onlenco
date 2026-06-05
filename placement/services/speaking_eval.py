"""Meaning-based scoring for placement SPEAKING answers.

Replaces brittle literal keyword-matching: a beginner answer that is correct
in meaning (e.g. "I'm software developer" — only missing the article "a")
must NOT be marked wrong. We ask the AI to judge each answer by meaning +
relevance, generously forgiving small grammar/article slips, and fall back
to a lenient heuristic when the AI is unavailable (offline / tests).

Cost: ONE batched AI call per finalise (all 5 answers at once), routed
through the ai_usage wrapper as feature=placement_speaking with
enforce_minutes=False — it NEVER consumes the paid AI-Tutor minutes.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    t = (text or "").lower().replace("’", "'")
    t = t.replace("i'm", "i am").replace("don't", "do not")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# Tokens that betray a speech-to-text language mis-detection (Turkish etc.).
_FOREIGN_TOKENS = {"yil", "yıl", "sonra", "evet", "hayir", "hayır", "naam", "yas", "yaş"}


def looks_non_english(text: str) -> bool:
    """Cheap heuristic: True when the transcript is clearly NOT English — a
    non-Latin script, a Turkish-specific letter, or a known foreign token.

    Used to flag a likely STT slip so we give partial 'uncertain' credit
    instead of a confident 'wrong'.
    """
    if not text:
        return False
    low = text.lower()
    for ch in low:
        if ch in "ışğ":              # Turkish dotless-i / ş / ğ
            return True
        if ord(ch) > 0x024F:         # beyond Latin → Arabic / Cyrillic / CJK …
            return True
    words = set(re.sub(r"[^a-zışğçöü\s]", " ", low).split())
    return bool(words & _FOREIGN_TOKENS)


_BATCH_PROMPT = (
    "You are scoring a beginner's spoken English PLACEMENT test. For each "
    "question and the student's spoken answer (which may contain "
    "speech-to-text errors), give a score 0-100 based on MEANING and "
    "relevance — NOT exact wording. Be generous: forgive small grammar or "
    "missing-article mistakes (e.g. 'I'm software developer' is a good "
    "answer). Guidance:\n"
    "- On-topic, understandable answer → 80-100.\n"
    "- Short but on-topic (e.g. just 'Software developer') → 65-85.\n"
    "- Partially relevant → 40-64.\n"
    "- Off-topic / irrelevant (e.g. 'thank you' to 'why do you want to learn "
    "English?') → below 35.\n"
    "- Empty or gibberish → below 20.\n"
    "Return JSON ONLY as {\"results\":[{\"score\":N,\"verdict\":\"correct|"
    "mostly_correct|partial|inappropriate\",\"feedback\":\"one short "
    "encouraging sentence (<=12 words)\"}]} in the SAME order as the items.\n\n"
    "Items:\n"
)


def score_speaking_answers(pairs: list[tuple[str, str]]) -> list[dict]:
    """Score a list of ``(question_text, student_answer)`` pairs.

    Returns a list (same order/length) of
    ``{"score": int, "verdict": str, "feedback": str}``.
    """
    results = [None] * len(pairs)
    to_ai = []
    for i, (q, a) in enumerate(pairs):
        if not (a or "").strip():
            results[i] = {"score": 0, "verdict": "empty", "feedback": ""}
        elif looks_non_english(a):
            # Likely STT mis-detection (e.g. "36 yıl sonra"): do NOT mark it a
            # confident wrong — give partial 'uncertain' credit so the learner
            # isn't penalised for a transcription error.
            results[i] = {"score": 50, "verdict": "stt_uncertain", "feedback": ""}
        else:
            to_ai.append(i)

    if to_ai:
        ai = None
        try:
            ai = _ai_score([(pairs[i][0], pairs[i][1]) for i in to_ai])
        except Exception:
            logger.warning("placement speaking AI scoring failed; using heuristic", exc_info=True)
        for n, i in enumerate(to_ai):
            if ai and n < len(ai) and ai[n]:
                results[i] = ai[n]
            else:
                results[i] = _heuristic(pairs[i][0], pairs[i][1])
    return [r or {"score": 0, "verdict": "empty", "feedback": ""} for r in results]


def _ai_score(pairs: list[tuple[str, str]]) -> list[dict] | None:
    from ai_usage import constants as C
    from ai_usage.services import ai_client

    lines = "".join(
        f"{n + 1}. Q: {q}\n   A: {a}\n" for n, (q, a) in enumerate(pairs)
    )
    text = ai_client.complete_text(
        _BATCH_PROMPT + lines,
        user=None,                       # skip the student-approval gate
        role=C.ROLE_STUDENT,
        feature=C.FEATURE_PLACEMENT_SPEAKING,
        enforce_minutes=False,           # NEVER consumes AI-Tutor minutes
    )
    return _parse(text, len(pairs))


def _parse(text: str, expected: int) -> list[dict] | None:
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):] if "{" in raw else raw
    try:
        data = json.loads(raw)
    except Exception:
        return None
    items = data.get("results") if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        return None
    out = []
    for it in items[:expected]:
        if not isinstance(it, dict):
            out.append(None)
            continue
        try:
            score = int(round(float(it.get("score", 0))))
        except (TypeError, ValueError):
            score = 0
        out.append({
            "score": max(0, min(100, score)),
            "verdict": str(it.get("verdict") or "partial")[:32],
            "feedback": str(it.get("feedback") or "").strip()[:160],
        })
    return out


def _heuristic(question: str, answer: str) -> dict:
    """Lenient offline fallback — never harshly punishes a real answer."""
    low = _normalize(answer)
    if not low:
        return {"score": 0, "verdict": "empty", "feedback": ""}
    n = len([w for w in low.split() if w])
    has_digit = any(c.isdigit() for c in low)
    if n >= 3:
        score, verdict = 85, "mostly_correct"
    elif n == 2:
        score, verdict = 75, "mostly_correct"
    elif has_digit:                 # a bare number like "36" answers an age question
        score, verdict = 75, "mostly_correct"
    else:
        score, verdict = 60, "partial"
    return {"score": score, "verdict": verdict, "feedback": ""}
