"""Bind each spoken placement answer to the RIGHT question.

The reliable path is live, per-question capture: while the call runs, the
browser POSTs each finalised student transcript together with the
``question_id`` that was being asked at that moment (see the
``placement_speaking_answer`` endpoint). The result page then reads those
stored ``PlacementAttemptQuestion.transcript`` values directly — it never
re-distributes a whole-conversation transcript.

This module also provides:
  * helpers to tell tutor turns / student turns / greetings apart,
  * ``extract_relevant_answer_for_question`` to keep only the clause that
    actually answers a question (so a rambling turn like
    "I come from Sudan. I am a teacher." doesn't dump everything onto one
    question, and Q5 never swallows the whole chat),
  * ``align_answers_by_explicit_question_state`` — a sequential state machine
    used ONLY as a fallback when no live answers were captured.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Pure social pleasantries — never a real answer.
_PLEASANTRIES = {
    "hi", "hello", "hey", "bye", "goodbye", "ok", "okay", "yes", "no",
    "thanks", "thank you", "thank you so much", "thanks a lot", "good bye",
    "see you", "nice to meet you", "no problem", "you too", "right", "great",
    "alright", "sure", "good",
}

# Cue words that identify WHICH fixed question a TUTOR turn is asking. Kept
# distinctive (no generic do/where/english) so the auto-start opening can't be
# mistaken for a later question.
_ASK_CUES = {
    "name": {"name"},
    "age": {"old", "age"},
    "country": {"from", "country", "nationality"},
    "job": {"living", "work", "job", "profession", "occupation"},
    "reason": {"learn", "reason", "why"},
}

# Broader cues used to decide whether a STUDENT clause answers a given key.
_ANSWER_CUES = {
    "name": {"name", "called", "i am", "i'm", "my name"},
    "age": {"old", "age", "year", "years"},
    "country": {"from", "country", "nationality", "sudan", "sudanese",
                "egypt", "egyptian", "saudi", "yemen", "born in"},
    "job": {"teacher", "work", "job", "developer", "engineer", "student",
            "assistant", "doctor", "nurse", "profession", "i work", "i am a",
            "manager", "accountant", "driver", "farmer", "business"},
    "reason": {"learn", "improve", "because", "communicate", "travel", "study",
               "need", "future", "career", "to get", "for my", "speak"},
}


def is_tutor_text(role: str) -> bool:
    return role == "assistant"


def is_student_text(role: str) -> bool:
    return role == "user"


def is_greeting_or_closing(text: str) -> bool:
    t = re.sub(r"[^a-z\s]", "", (text or "").lower()).strip()
    t = re.sub(r"\s+", " ", t)
    return t in _PLEASANTRIES


def question_key(question) -> str | None:
    """Map a fixed placement question to a semantic key."""
    t = (getattr(question, "question_text", "") or "").lower()
    if "name" in t:
        return "name"
    if "old" in t or "age" in t:
        return "age"
    if "from" in t or "where are you" in t or "country" in t:
        return "country"
    if "living" in t or "do you do" in t or "work" in t or "job" in t:
        return "job"
    if "learn" in t or "why" in t:
        return "reason"
    return None


def question_cues(question) -> set[str]:
    """Cue words that mark a tutor turn as asking this question."""
    key = question_key(question)
    if key and key in _ASK_CUES:
        return set(_ASK_CUES[key])
    return {w for w in re.findall(r"[a-z]+", (getattr(question, "question_text", "") or "").lower())
            if len(w) > 3}


def tutor_asked_question(question, assistant_text: str) -> bool:
    low = (assistant_text or "").lower()
    return any(cue in low for cue in question_cues(question))


def _clause_matches_key(clause: str, key: str | None) -> bool:
    if not key:
        return False
    low = clause.lower()
    if key == "age" and re.search(r"\d", low):
        return True
    return any(cue in low for cue in _ANSWER_CUES.get(key, set()))


def extract_relevant_answer_for_question(question, transcript: str) -> str:
    """Keep only the clause(s) of ``transcript`` that answer ``question``.

    A single-clause answer is returned unchanged. A multi-clause / rambling
    transcript is split on sentence boundaries and only the clauses matching
    this question's key are kept — so a country answer doesn't keep the job
    clause, and Q5 never swallows name/age/country/job sentences. When nothing
    can be matched the whole text is kept (better to show too much than lose
    the answer), with a debug log.
    """
    text = (transcript or "").strip()
    if not text:
        return ""
    clauses = [c.strip() for c in re.split(r"(?<=[.!?])\s+|[.!?]+", text) if c.strip()]
    if len(clauses) <= 1:
        return text
    key = question_key(question)
    relevant = [c for c in clauses if _clause_matches_key(c, key)]
    if relevant:
        trimmed = ". ".join(relevant).strip()
        if trimmed != text:
            logger.debug("placement: trimmed multi-clause answer for key=%s", key)
        return trimmed
    logger.debug("placement: could not segment answer for key=%s; keeping whole", key)
    return text


def align_answers_by_explicit_question_state(rows, turns) -> tuple[list[str], list[str]]:
    """FALLBACK only. Replay ``turns`` (list of ``{"role","content"}``) and bind
    each student turn to the question the tutor most-recently asked (advancing
    one question at a time). Returns ``(answers, warnings)`` aligned to ``rows``.
    Never stores tutor/greeting text as an answer.
    """
    answers = [""] * len(rows)
    warnings: list[str] = []
    current = -1
    for t in turns:
        content = (t.get("content") or "").strip()
        if not content:
            continue
        if is_tutor_text(t.get("role")):
            nxt = current + 1
            if nxt < len(rows) and tutor_asked_question(rows[nxt].question, content):
                current = nxt
        elif is_student_text(t.get("role")):
            if is_greeting_or_closing(content):
                continue
            if current < 0:
                warnings.append(f"student spoke before any question: {content[:60]!r}")
                continue
            answers[current] = (
                (answers[current] + " " + content).strip() if answers[current] else content
            )
    # Trim each bound answer to the clause(s) that actually answer its question.
    out = [extract_relevant_answer_for_question(r.question, answers[i])
           for i, r in enumerate(rows)]
    return out, warnings
