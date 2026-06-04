"""Deterministic answer-key helpers for placement questions.

The question bank stores the correct answer as:
- MCQ:   ``options = [{"text": ..., "is_correct": bool}, ...]``
- text:  ``scoring_rubric["expected_answer"]`` (+ ``accepted_answers``)
- voice: ``scoring_rubric["voice_keywords"]``

These helpers expose that key so the result page can show ✓/✗ and the
correct answer, and so MCQ scoring can be graded against the real key
(instead of mere option-validity). Legacy questions whose options are flat
strings (no key) return ``None`` for correctness — those stay AI/heuristic
graded.
"""
from __future__ import annotations


def _option_pairs(options):
    """[(text, is_correct_or_None)] from dict-options or legacy string-options."""
    pairs = []
    for opt in (options or []):
        if isinstance(opt, dict):
            pairs.append(((opt.get("text") or "").strip(), bool(opt.get("is_correct"))))
        else:
            pairs.append((str(opt).strip(), None))
    return pairs


def correct_answer_for(*, options=None, rubric=None, expected_type: str = "") -> str:
    """A human-readable correct/expected answer, or "" when none is stored."""
    rubric = rubric or {}
    if expected_type == "mcq":
        for text, is_correct in _option_pairs(options):
            if is_correct:
                return text
        return ""
    if expected_type == "voice":
        kws = rubric.get("voice_keywords") or []
        if isinstance(kws, (list, tuple)):
            return "، ".join(str(k) for k in kws if k)
        return str(kws or "")
    # short_text / sentence / paragraph
    return (rubric.get("expected_answer") or "").strip()


def is_answer_correct(answer, *, options=None, rubric=None, expected_type: str = ""):
    """True / False when the answer can be graded deterministically against a
    stored key, else None (no key → leave to the rubric/AI score)."""
    text = (answer or "").strip().lower()
    rubric = rubric or {}
    if expected_type == "mcq":
        pairs = _option_pairs(options)
        if not any(ok is True for _, ok in pairs):
            return None  # legacy options without a key
        if not text:
            return False
        return any(ok and opt.strip().lower() == text for opt, ok in pairs)
    if expected_type in {"short_text", "sentence", "paragraph"}:
        expected = (rubric.get("expected_answer") or "").strip().lower()
        accepted = [str(a).strip().lower() for a in (rubric.get("accepted_answers") or [])]
        if not expected and not accepted:
            return None  # open-ended → graded by rubric, not exact match
        if not text:
            return False
        return text == expected or text in accepted
    return None  # voice / unknown → graded by score
