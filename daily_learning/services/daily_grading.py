"""Server-side grading for Daily Quiz items (Prompt 18.3B).

Grading was previously done in the browser (the correct answer was leaked into
the DOM and the server never checked it). This module is the single backend
authority: it compares the student's answer to the item's stored
``correct_answer`` with light, meaning-preserving normalisation — by TEXT and
TOKENS, never by option index.

Supported shapes:
  * MCQ / quiz / vocabulary / listening / reading / writing
        payload {"answer": "<text>"}  → normalised string compare.
  * word_order (incl. listen_build_sentence = word_order + metadata.listen_build)
        payload {"tokens": [...]} or {"answer": "w1 w2 ..."}
        → normalised TOKEN-ORDER compare.

Pure functions, no DB writes; returns a plain dict.
"""
from __future__ import annotations

import re

_EDGE_PUNCT = ".,!?;:'\"()[]{}…”“’‘-—–"


def _collapse(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def normalize_text(s: str) -> str:
    """Lower, trim, collapse inner spaces, strip simple edge punctuation."""
    s = _collapse(s).lower()
    return s.strip(_EDGE_PUNCT).strip()


def normalize_tokens(value) -> list[str]:
    """Tokenise to a normalised list. Accepts a list of words or a string."""
    if isinstance(value, (list, tuple)):
        raw = [str(t) for t in value]
    else:
        raw = _collapse(str(value or "")).split(" ")
    out = []
    for t in raw:
        t = t.strip().lower().strip(_EDGE_PUNCT).strip()
        if t:
            out.append(t)
    return out


def is_word_order_item(item) -> bool:
    if getattr(item, "item_type", "") == "word_order":
        return True
    return bool((getattr(item, "metadata", None) or {}).get("listen_build"))


def grade_item(item, payload: dict | None = None) -> dict:
    """Grade one Daily Quiz item server-side.

    Returns ``{is_correct, score, normalized_answer, expected, question_type}``.
    Never trusts any client-provided correctness flag. ``expected`` is for
    internal/test use — callers must NOT forward it to the student.
    """
    payload = payload or {}
    qtype = getattr(item, "item_type", "") or ""
    listen_build = bool((getattr(item, "metadata", None) or {}).get("listen_build"))
    correct = getattr(item, "correct_answer", "") or ""

    if is_word_order_item(item):
        submitted = payload.get("tokens")
        if submitted is None:
            submitted = payload.get("answer", "")
        got = normalize_tokens(submitted)
        expected = normalize_tokens(correct)
        is_correct = bool(expected) and got == expected
        return {
            "is_correct": is_correct,
            "score": 1 if is_correct else 0,
            "gradable": bool(expected),
            "normalized_answer": " ".join(got),
            "expected": " ".join(expected),
            "question_type": "listen_build_sentence" if listen_build else "word_order",
        }

    # MCQ / quiz / vocabulary / listening / reading / writing — text compare.
    ans = normalize_text(str(payload.get("answer", "")))
    expected = normalize_text(correct)
    # Accept either an exact match to correct_answer or, defensively, an exact
    # match to whichever option equals it (still text, never index).
    is_correct = bool(expected) and ans == expected
    return {
        "is_correct": is_correct,
        "score": 1 if is_correct else 0,
        # Items with no correct_answer (motivation, speaking, plain vocabulary
        # display) are NOT scored — they don't count toward correctness.
        "gradable": bool(expected),
        "normalized_answer": ans,
        "expected": expected,
        "question_type": qtype or "quiz",
    }
