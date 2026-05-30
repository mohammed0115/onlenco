"""Per-type graders for the 20 question types in the registry.

Every grader has the same signature:

    grader(question, raw_response) -> dict

with at minimum:

    is_correct (bool)
    score      (float in [0, 1])
    feedback_en, feedback_ar (str)

The dispatcher `grade` reads the registry's `grader` key, calls the
matching function below, and falls through to `_noop_grade` for
anything unknown so a card never 500s.
"""
from __future__ import annotations

import json
import re
from typing import Any

from courses.services import question_type_registry as registry


# ---------------------------------------------------------------------------
# Tiny helpers
# ---------------------------------------------------------------------------

def _norm(text) -> str:
    """Lowercase + strip + collapse whitespace + drop terminal punctuation.

    Used everywhere a forgiving equality check is appropriate (i.e. most
    text inputs in beginner cards).
    """
    if text is None:
        return ""
    text = str(text).strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(".!?,;:")
    return text


def _decode(raw) -> Any:
    """Best-effort JSON decode of a stringified payload (the form layer
    coerces complex values to text). Falls back to the raw value."""
    if not isinstance(raw, str):
        return raw
    s = raw.strip()
    if s.startswith(("{", "[")):
        try:
            return json.loads(s)
        except Exception:
            pass
    return raw


def _ok(*, score: float = 1.0, en: str = "", ar: str = "") -> dict:
    return {"is_correct": score == 1.0, "score": float(score),
            "feedback_en": en, "feedback_ar": ar}


def _ko(*, score: float = 0.0, en: str = "", ar: str = "") -> dict:
    return {"is_correct": False, "score": float(score),
            "feedback_en": en, "feedback_ar": ar}


# ---------------------------------------------------------------------------
# 1. tap_choice / image_choice / listen_and_choose / sound_to_word /
#    mini_story_choice / conversation_reply / translate_to_arabic
#    — all share the "select an option by id (or value)" rubric.
# ---------------------------------------------------------------------------

def grade_tap_choice(question, raw) -> dict:
    md = question.metadata or {}
    target = md.get("correct_option_id") or _norm(question.correct_answer)
    chosen = _norm(raw)
    if not target:
        return _ko(en="No correct answer is configured for this card.",
                   ar="هذا السؤال بدون إجابة محددة.")
    if chosen == _norm(target):
        return _ok()
    # Also accept matching the option's `text` field, not just its id.
    for opt in (md.get("options") or []):
        if str(opt.get("id", "")) == str(target):
            if _norm(opt.get("text", "")) == chosen:
                return _ok()
            break
    return _ko(en=f"The answer was: {target}",
               ar=f"الإجابة الصحيحة: {target}")


# ---------------------------------------------------------------------------
# 2. listen_and_type — typed response compared to a transcript.
# ---------------------------------------------------------------------------

def grade_listen_and_type(question, raw) -> dict:
    md = question.metadata or {}
    target = md.get("correct_answer") or question.correct_answer or ""
    if _norm(raw) == _norm(target):
        return _ok()
    return _ko(en=f"The line was: \"{target}\"",
               ar=f"الجملة المسموعة: \"{target}\"")


# ---------------------------------------------------------------------------
# 3. picture_labeling / translate_to_english — accept a set of variants.
# ---------------------------------------------------------------------------

def grade_accepted_answers(question, raw) -> dict:
    md = question.metadata or {}
    accepted = [_norm(a) for a in (md.get("accepted_answers") or [])]
    if not accepted and question.correct_answer:
        accepted = [_norm(question.correct_answer)]
    chosen = _norm(raw)
    if chosen and chosen in accepted:
        return _ok()
    show = accepted[0] if accepted else "—"
    return _ko(en=f"Accepted answers include: {show}",
               ar=f"من الإجابات المقبولة: {show}")


# ---------------------------------------------------------------------------
# 4. word_bank_sentence — student-built word order vs target.
# ---------------------------------------------------------------------------

def grade_word_bank_sentence(question, raw) -> dict:
    md = question.metadata or {}
    correct = list(md.get("correct_order") or [])
    if not correct:
        return grade_normalize_equality(question, raw)

    decoded = _decode(raw)
    if isinstance(decoded, list):
        chosen = [_norm(w) for w in decoded]
    else:
        # Accept pipe / space-separated strings from simpler renderers.
        s = str(raw or "").strip()
        parts = re.split(r"[|\s]+", s) if s else []
        chosen = [_norm(p) for p in parts if p]

    if chosen == [_norm(w) for w in correct]:
        return _ok()
    target = " ".join(correct)
    return _ko(en=f"Word order: \"{target}\"",
               ar=f"الترتيب الصحيح: \"{target}\"")


# ---------------------------------------------------------------------------
# 5. match_pairs — partial credit per correct pair.
# ---------------------------------------------------------------------------

def grade_match_pairs(question, raw) -> dict:
    md = question.metadata or {}
    pairs = md.get("pairs") or []
    if not pairs:
        return _noop_grade(question, raw)

    decoded = _decode(raw)
    submitted: dict = {}
    if isinstance(decoded, dict):
        submitted = {str(k): str(v) for k, v in decoded.items()}

    hits = 0
    for pair in pairs:
        left = str(pair.get("left", ""))
        right = str(pair.get("right", ""))
        if _norm(submitted.get(left, "")) == _norm(right):
            hits += 1
    score = hits / len(pairs) if pairs else 0.0
    is_correct = score == 1.0
    return {
        "is_correct": is_correct,
        "score": score,
        "feedback_en": "" if is_correct else f"{hits}/{len(pairs)} pairs matched.",
        "feedback_ar": "" if is_correct else f"{hits}/{len(pairs)} مطابقة صحيحة.",
    }


# ---------------------------------------------------------------------------
# 6. normalize_equality — used by fill_blank_card + most legacy types.
# ---------------------------------------------------------------------------

def grade_normalize_equality(question, raw) -> dict:
    target = _norm(question.correct_answer)
    chosen = _norm(raw)
    if target and chosen == target:
        return _ok()
    return _ko(en=f"Expected: {question.correct_answer}" if question.correct_answer else "",
               ar=f"الإجابة المتوقعة: {question.correct_answer}" if question.correct_answer else "")


# ---------------------------------------------------------------------------
# 7. frequency_scale — single target with tolerance (uses metadata.target).
# ---------------------------------------------------------------------------

def grade_frequency_scale(question, raw) -> dict:
    md = question.metadata or {}
    target = md.get("target") or {}
    label = target.get("label")
    target_pct = target.get("percent")
    if label is None or target_pct is None:
        # Fall back to the v2 multi-target shape from the Quiz Engine.
        from courses.services.quiz_grader import grade_frequency_scale as v2_grade
        return v2_grade(question, raw)
    tolerance = float(md.get("tolerance", 10))

    decoded = _decode(raw)
    got_pct = None
    if isinstance(decoded, dict):
        if label in decoded:
            got_pct = decoded[label]
        elif "percent" in decoded:
            got_pct = decoded["percent"]
    else:
        try:
            got_pct = float(str(raw).strip().rstrip("%"))
        except Exception:
            got_pct = None
    if got_pct is None:
        return _ko(en=f"Place '{label}' near {target_pct}%.",
                   ar=f"ضع '{label}' بالقرب من {target_pct}٪.")
    try:
        within = abs(float(got_pct) - float(target_pct)) <= tolerance
    except Exception:
        within = False
    if within:
        return _ok()
    return _ko(en=f"'{label}' belongs near {target_pct}%.",
               ar=f"'{label}' تنتمي إلى ما يقارب {target_pct}٪.")


# ---------------------------------------------------------------------------
# 8. table_sentence_builder — re-uses the v2 grader (already correct).
# ---------------------------------------------------------------------------

def grade_table_sentence_builder(question, raw) -> dict:
    from courses.services.quiz_grader import grade_table_sentence_builder as v2_grade
    return v2_grade(question, raw)


# ---------------------------------------------------------------------------
# 9. question_transform — re-uses the v2 grader.
# ---------------------------------------------------------------------------

def grade_question_transform(question, raw) -> dict:
    from courses.services.quiz_grader import grade_question_transform as v2_grade
    return v2_grade(question, raw)


# ---------------------------------------------------------------------------
# 10. mistake_correction — student's corrected sentence vs target.
# ---------------------------------------------------------------------------

def grade_mistake_correction(question, raw) -> dict:
    md = question.metadata or {}
    target = md.get("corrected_sentence") or question.correct_answer or ""
    if _norm(raw) == _norm(target):
        return _ok()
    # Accept variants if provided.
    for alt in (md.get("accepted_answers") or []):
        if _norm(raw) == _norm(alt):
            return _ok()
    return _ko(en=f"The fix is: \"{target}\"",
               ar=f"الصواب: \"{target}\"")


# ---------------------------------------------------------------------------
# 11. Placeholders — self-check / "noted" — never block the session.
# ---------------------------------------------------------------------------

def grade_self_check(question, raw) -> dict:
    """Speaking / pronunciation / AI roleplay placeholders.

    Phase 3 doesn't ship real STT or AI feedback. We accept the card
    as "noted" so the Challenge keeps moving and the student isn't
    punished for an unimplemented capability. Real grading will come
    when those services land.
    """
    return {
        "is_correct": True,    # don't fail the student on placeholders
        "score": 1.0,
        "feedback_en": "Speaking practice recorded as completed. AI feedback will be added in a later phase.",
        "feedback_ar": "تم تسجيل التدريب الصوتي كمكتمل. تقييم الذكاء الاصطناعي سيأتي في مرحلة قادمة.",
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

GRADERS = {
    "tap_choice":             grade_tap_choice,
    "listen_and_type":        grade_listen_and_type,
    "accepted_answers":       grade_accepted_answers,
    "word_bank_sentence":     grade_word_bank_sentence,
    "match_pairs":            grade_match_pairs,
    "normalize_equality":     grade_normalize_equality,
    "frequency_scale":        grade_frequency_scale,
    "table_sentence_builder": grade_table_sentence_builder,
    "question_transform":     grade_question_transform,
    "mistake_correction":     grade_mistake_correction,
    "self_check":             grade_self_check,
}


def _noop_grade(question, raw) -> dict:
    """Fallback for unknown grader keys. Same shape as a real result."""
    return {
        "is_correct": False,
        "score": 0.0,
        "feedback_en": "This card type is not gradable yet.",
        "feedback_ar": "هذا النوع غير قابل للتصحيح الآن.",
    }


def grade(question, raw_response: Any) -> dict:
    """Top-level grade dispatcher. Uses the registry to pick the function."""
    key = registry.grader_key(question.question_type)
    fn = GRADERS.get(key, _noop_grade)
    return fn(question, raw_response)
