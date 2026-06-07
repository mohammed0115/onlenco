"""Post-call AI reconciliation for placement SPEAKING answers.

After a placement speaking call ends we have two imperfect signals:

  * the LIVE per-question answers (POSTed during the call with a question_id),
  * the full raw transcript (every tutor + student turn, in order).

Live capture is usually right, but real calls are noisy: a student may say a
filler ("I'm not going to finish that one…") that gets bound to a question
before the real answer arrives, or pack two answers into one turn
("I come from Sudan. I am a teacher."), or answer Q5 in a way that swallows
the whole chat. This module asks the AI to produce a CLEAN answer mapping —
one clean answer per question — BEFORE scoring.

It is NOT a grader: it never assigns a score or a CEFR level. It only
re-aligns + cleans. Scoring stays in ``speaking_eval``.

Cost: ONE batched AI call per finalise, routed through the ai_usage wrapper as
feature=placement_reconcile with enforce_minutes=False — it is NOT a
minute-bearing feature, so it NEVER consumes the paid AI-Tutor minutes.
A local, deterministic fallback keeps the result safe when the AI is
unavailable (offline / disabled / error).
"""
from __future__ import annotations

import json
import logging
import re

from django.conf import settings

from placement.services import speaking_alignment as sa

logger = logging.getLogger(__name__)

# The five fixed placement questions, keyed semantically. Order is canonical.
BASE_QUESTIONS = [
    ("name", "What is your name?"),
    ("age", "How old are you?"),
    ("country", "Where are you from?"),
    ("job", "What do you do for a living?"),
    ("reason", "Why do you want to learn English?"),
]

MAX_CLEAN_CHARS = 240          # an answer longer than this is almost certainly a smear
MAX_TURNS_IN_PROMPT = 60       # bound the prompt size


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def reconcile_speaking_answers(attempt, conversation_turns, live_answers):
    """Produce a clean answer mapping for ``attempt``'s speaking questions.

    Args:
      attempt: the PlacementAttempt.
      conversation_turns: list of ``{"role", "content"[, "timestamp"]}`` — the
        full raw transcript in order.
      live_answers: list of candidate answers aligned 1:1 with the ordered
        speaking rows (the live-captured / hybrid transcript per question).

    Returns a dict:
      ``{"answers": [{question_id, question_order, question_key, clean_answer,
                      confidence, source, ignored_noise, needs_review}],
         "global_warnings": [...]}``
    The ``answers`` list is ordered to match the ordered speaking rows.
    """
    rows = list(
        attempt.questions.filter(section="speaking")
        .select_related("question").order_by("order")
    )
    candidates = _coerce_candidates(rows, live_answers)
    turns = list(conversation_turns or [])
    warnings: list[str] = []

    if getattr(settings, "PLACEMENT_USE_AI_RECONCILIATION", True):
        data = None
        try:
            data = _ai_reconcile(rows, turns, candidates)
        except Exception:
            logger.warning(
                "placement reconciliation AI failed (attempt=%s); using fallback",
                getattr(attempt, "id", "?"), exc_info=True,
            )
            warnings.append("reconciliation_failed")
        if data is not None:
            return _build_from_ai(data, rows, turns, candidates, warnings)
        if "reconciliation_failed" not in warnings:
            # AI returned nothing usable but didn't raise.
            warnings.append("reconciliation_empty")

    return _fallback(rows, turns, candidates, warnings)


# ---------------------------------------------------------------------------
# Candidate normalisation + small text helpers
# ---------------------------------------------------------------------------

def _coerce_candidates(rows, live_answers) -> list[str]:
    """Return a list of candidate answers aligned to ``rows``."""
    if isinstance(live_answers, dict):
        return [str(live_answers.get(r.id) or "").strip() for r in rows]
    seq = list(live_answers or [])
    out = []
    for i, _r in enumerate(rows):
        out.append(str(seq[i]).strip() if i < len(seq) and seq[i] else "")
    return out


def _norm(text: str) -> str:
    t = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def _student_blob(turns, candidates) -> str:
    """All student-spoken text (lowercased), used to reject invented answers."""
    parts = [c for c in candidates if c]
    for t in turns:
        if sa.is_student_text(t.get("role")):
            parts.append(t.get("content") or "")
    return _norm(" ".join(parts))


def _tutor_blob(turns) -> str:
    parts = [t.get("content") or "" for t in turns if sa.is_tutor_text(t.get("role"))]
    return _norm(" ".join(parts))


def _has_student_overlap(clean: str, student_blob: str) -> bool:
    """True when a meaningful word of ``clean`` appears in the student speech —
    a cheap anti-invention guard."""
    words = [w for w in _norm(clean).split() if len(w) > 3]
    if not words:
        # Very short answers (e.g. a bare number for age) — accept if any token
        # is present at all.
        return all(w in student_blob for w in _norm(clean).split()) if clean else False
    return any(w in student_blob for w in words)


def _looks_like_tutor(clean: str, tutor_blob: str) -> bool:
    n = _norm(clean)
    return bool(n) and len(n) > 8 and n in tutor_blob


def _cap(clean: str) -> str:
    """Keep at most the first two sentences / MAX_CLEAN_CHARS — stops any one
    answer (esp. Q5) from swallowing the whole conversation."""
    text = (clean or "").strip()
    if not text:
        return ""
    clauses = [c.strip() for c in re.split(r"(?<=[.!?])\s+", text) if c.strip()]
    if len(clauses) > 2:
        text = " ".join(clauses[:2])
    return text[:MAX_CLEAN_CHARS].strip()


# ---------------------------------------------------------------------------
# AI path
# ---------------------------------------------------------------------------

_PROMPT = (
    "You are aligning a beginner English placement speaking transcript. Your "
    "task is to map the learner's spoken answers to the correct placement "
    "questions. Ignore tutor messages, greetings, filler, accidental speech, "
    "and closing phrases (hello, ok, thanks, right, and a bare 'yes'/'no' when "
    "it is not a sufficient answer). Do not invent answers. Do not use the "
    "tutor's words as a student answer. If one student turn contains two "
    "answers (e.g. 'I come from Sudan. I am a teacher.'), split them to the "
    "matching questions. Never assign a score or a CEFR level. Return JSON "
    "ONLY, no prose.\n\n"
    "Output schema:\n"
    '{"answers":[{"question_id":N,"question_order":N,"question_key":"name|age|'
    'country|job|reason","clean_answer":"...","confidence":0.0-1.0,"source":'
    '"live_capture|transcript","ignored_noise":["..."],"needs_review":false}],'
    '"global_warnings":[]}\n'
    "Rules: clean_answer is the student's own words, lightly tidied. If you "
    "cannot find a clear answer, set clean_answer to \"\", confidence low, and "
    "needs_review true. Keep a clean_answer short (one short sentence).\n\n"
)


def _ai_reconcile(rows, turns, candidates):
    from ai_usage import constants as C
    from ai_usage.services import ai_client

    q_lines = []
    for i, r in enumerate(rows):
        key = sa.question_key(r.question) or ""
        q_lines.append(
            f'  - question_id={r.id}, order={r.order}, key="{key}", '
            f'text="{(r.question.question_text or "").strip()}", '
            f'live_answer="{candidates[i]}"'
        )
    t_lines = []
    for t in turns[-MAX_TURNS_IN_PROMPT:]:
        role = "TUTOR" if sa.is_tutor_text(t.get("role")) else "STUDENT"
        content = (t.get("content") or "").strip()
        if not content:
            continue
        ts = t.get("timestamp")
        stamp = f" @{ts}" if ts else ""
        t_lines.append(f"  {role}{stamp}: {content}")

    prompt = (
        _PROMPT
        + "Placement questions (in order):\n" + "\n".join(q_lines)
        + "\n\nRaw transcript (in order):\n" + "\n".join(t_lines)
        + "\n\nReturn the JSON mapping now."
    )
    text = ai_client.complete_text(
        prompt,
        user=None,                        # skip the student-approval gate
        role=C.ROLE_STUDENT,
        feature=C.FEATURE_PLACEMENT_RECONCILE,
        enforce_minutes=False,            # NEVER consumes AI-Tutor minutes
    )
    return _parse(text)


def _parse(text):
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
    if not isinstance(data, dict) or not isinstance(data.get("answers"), list):
        return None
    return data


def _build_from_ai(data, rows, turns, candidates, warnings):
    student_blob = _student_blob(turns, candidates)
    tutor_blob = _tutor_blob(turns)
    by_id = {}
    for item in data.get("answers") or []:
        if isinstance(item, dict) and item.get("question_id") is not None:
            try:
                by_id[int(item["question_id"])] = item
            except (TypeError, ValueError):
                continue

    answers = []
    for i, r in enumerate(rows):
        item = by_id.get(r.id)
        if item is None:
            answers.append(_fallback_entry(r, candidates[i]))
            continue
        answers.append(_clean_entry(r, item, candidates[i], student_blob, tutor_blob))

    gw = data.get("global_warnings")
    gw = [str(x) for x in gw] if isinstance(gw, list) else []
    gw.extend(warnings)
    return {"answers": answers, "global_warnings": gw}


def _clean_entry(row, item, candidate, student_blob, tutor_blob):
    key = sa.question_key(row.question) or ""
    clean = _cap(str(item.get("clean_answer") or "").strip())
    ignored = item.get("ignored_noise")
    ignored = [str(x) for x in ignored] if isinstance(ignored, list) else []
    try:
        confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    needs_review = bool(item.get("needs_review", False))
    source = str(item.get("source") or "live_capture")[:32]

    # Guard 1: never accept a pleasantry as an answer.
    if clean and sa.is_greeting_or_closing(clean):
        clean, needs_review, confidence = "", True, min(confidence, 0.2)
    # Guard 2: never accept the tutor's own words.
    if clean and _looks_like_tutor(clean, tutor_blob):
        clean, needs_review, confidence = "", True, min(confidence, 0.2)
    # Guard 3: anti-invention — the answer must echo something the student said.
    if clean and student_blob and not _has_student_overlap(clean, student_blob):
        # Prefer the live candidate (trimmed) over an invented sentence.
        fb = sa.extract_relevant_answer_for_question(row.question, candidate)
        clean = _cap(fb)
        source = "live_capture"
        needs_review = True
        confidence = min(confidence, 0.3)

    if not clean:
        needs_review = True
        confidence = min(confidence, 0.2)

    return {
        "question_id": row.id,
        "question_order": row.order,
        "question_key": key,
        "clean_answer": clean,
        "confidence": round(confidence, 2),
        "source": source,
        "ignored_noise": ignored[:10],
        "needs_review": needs_review,
    }


# ---------------------------------------------------------------------------
# Local deterministic fallback (AI disabled / unavailable / empty)
# ---------------------------------------------------------------------------

def _fallback(rows, turns, candidates, warnings):
    answers = [_fallback_entry(r, candidates[i]) for i, r in enumerate(rows)]
    return {"answers": answers, "global_warnings": list(warnings)}


def _fallback_entry(row, candidate):
    key = sa.question_key(row.question) or ""
    # Keep the clause(s) that actually answer THIS question, drop pleasantries.
    clean = sa.extract_relevant_answer_for_question(row.question, candidate or "")
    if clean and sa.is_greeting_or_closing(clean):
        clean = ""
    clean = _cap(clean)
    needs_review = not bool(clean)
    return {
        "question_id": row.id,
        "question_order": row.order,
        "question_key": key,
        "clean_answer": clean,
        "confidence": 0.6 if clean else 0.0,
        "source": "live_capture",
        "ignored_noise": [],
        "needs_review": needs_review,
    }
