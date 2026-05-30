"""Per-question_type grading for the Onlenco Quiz Engine.

One pure function per type — `grade_<type>(question, raw_response)` → a
result dict with at least these keys:
  - is_correct: bool
  - score:      float in [0, 1]
  - feedback_en, feedback_ar: optional short notes shown back to the
                              student after submission

The dispatcher `grade_question(question, raw_response)` picks the right
grader. Legacy types (`multiple_choice`, `fill_blank`, …) keep their
existing case-insensitive string-equality behaviour.
"""
from __future__ import annotations

import re
from typing import Any


def _norm(text: str) -> str:
    """Lowercase, strip outer whitespace, collapse internal whitespace,
    drop terminal punctuation. Used for forgiving string comparison."""
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = text.rstrip(".!?,;:")
    return text


# -------- legacy types -----------------------------------------------------

def _grade_legacy_equality(question, raw_response: str) -> dict:
    chosen = _norm(raw_response or "")
    correct = _norm(question.correct_answer or "")
    is_correct = bool(correct) and chosen == correct
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else 0.0,
        "feedback_en": "" if is_correct else f"Expected: {question.correct_answer}",
        "feedback_ar": "" if is_correct else "الإجابة الصحيحة موضحة أعلاه.",
    }


# -------- new interactive types -------------------------------------------

def grade_sentence_ordering(question, raw_response: Any) -> dict:
    """Compare the student's word order to `metadata.correct_order`.

    `raw_response` may arrive as:
      - a list of words (preferred, from the JSON form field), or
      - a delimited string (newline / comma / pipe separated).
    """
    correct = list(question.metadata.get("correct_order") or question.options or [])
    if not correct:
        return _grade_legacy_equality(question, raw_response)

    if isinstance(raw_response, str):
        parts = re.split(r"[|\n,]", raw_response)
        chosen = [p.strip() for p in parts if p.strip()]
    elif isinstance(raw_response, list):
        chosen = [str(p).strip() for p in raw_response if str(p).strip()]
    else:
        chosen = []

    is_correct = [_norm(w) for w in chosen] == [_norm(w) for w in correct]
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else 0.0,
        "feedback_en": "" if is_correct else "Word order is off — try again.",
        "feedback_ar": "" if is_correct else "ترتيب الكلمات غير صحيح — حاول مرة أخرى.",
    }


def grade_frequency_scale(question, raw_response: Any) -> dict:
    """Each item carries a target percent. Student response is a dict of
    {word: percent} or {word: position}. We grade per word with a
    tolerance from `metadata.tolerance` (default ±10%)."""
    items = question.metadata.get("scale_items") or []
    if not items:
        return _grade_legacy_equality(question, raw_response)
    tolerance = float(question.metadata.get("tolerance", 10.0))

    submitted: dict = {}
    if isinstance(raw_response, dict):
        submitted = {str(k): _to_percent(v) for k, v in raw_response.items()}
    elif isinstance(raw_response, str):
        # parse "word=42; word=80" or JSON dict
        try:
            import json
            submitted = {k: _to_percent(v) for k, v in json.loads(raw_response).items()}
        except Exception:
            for pair in re.split(r"[;,\n]", raw_response):
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    submitted[k.strip()] = _to_percent(v)

    hits = 0
    total = 0
    for it in items:
        word = (it.get("word") or "").strip()
        if not word:
            continue
        target = float(it.get("percent", 0))
        got = submitted.get(word, submitted.get(word.lower()))
        if got is not None and abs(float(got) - target) <= tolerance:
            hits += 1
        total += 1
    score = (hits / total) if total else 0.0
    return {
        "is_correct": score == 1.0,
        "score": score,
        "feedback_en": "" if score == 1.0 else f"{hits}/{total} words placed within tolerance.",
        "feedback_ar": "" if score == 1.0 else f"{hits}/{total} كلمات في الموضع الصحيح.",
    }


def _to_percent(v) -> float | None:
    try:
        return float(str(v).rstrip("%"))
    except Exception:
        return None


def grade_table_sentence_builder(question, raw_response: Any) -> dict:
    """Student types `min_sentences` sentences (one per line). We check
    each sentence for the 4 ingredients defined in `metadata.columns`:
    subject, frequency adverb, activity, time phrase. A sentence is
    accepted if it contains at least one token from each of the 4
    columns (case-insensitive, word-boundary)."""
    columns = question.metadata.get("columns") or {}
    if not columns:
        return _grade_legacy_equality(question, raw_response)
    min_sentences = int(question.metadata.get("min_sentences", 5))

    sentences = []
    if isinstance(raw_response, list):
        sentences = [str(s).strip() for s in raw_response if str(s).strip()]
    elif isinstance(raw_response, str):
        sentences = [s.strip() for s in raw_response.splitlines() if s.strip()]

    def has_any(text: str, tokens) -> bool:
        """True if any token (or its meaningful keyword) appears in `text`."""
        for tok in (tokens or []):
            tok_str = str(tok).strip()
            if not tok_str:
                continue
            # Try the full phrase first…
            if re.search(rf"\b{re.escape(tok_str)}\b", text, re.IGNORECASE):
                return True
            # …then fall back to the last word, which for activities is
            # the noun/object (e.g. "play soccer" → "soccer") and lets
            # the student conjugate the verb naturally ("plays soccer").
            parts = tok_str.split()
            if len(parts) >= 2 and re.search(
                rf"\b{re.escape(parts[-1])}\b", text, re.IGNORECASE,
            ):
                return True
        return False

    accepted = 0
    for sent in sentences:
        if all(has_any(sent, columns.get(col)) for col in ("subject", "frequency", "activity", "time")):
            accepted += 1

    score = min(1.0, accepted / max(1, min_sentences))
    is_correct = accepted >= min_sentences
    return {
        "is_correct": is_correct,
        "score": score,
        "feedback_en": (
            f"Accepted {accepted}/{min_sentences} sentences."
            if not is_correct else ""
        ),
        "feedback_ar": (
            f"تم قبول {accepted}/{min_sentences} جملة."
            if not is_correct else ""
        ),
    }


def grade_listening_match(question, raw_response: Any) -> dict:
    """Student matches each activity to a frequency adverb. Response is
    a dict of {activity: answer}."""
    pairs = question.metadata.get("pairs") or []
    if not pairs:
        return _grade_legacy_equality(question, raw_response)

    submitted = {}
    if isinstance(raw_response, dict):
        submitted = {str(k): str(v) for k, v in raw_response.items()}
    elif isinstance(raw_response, str):
        try:
            import json
            submitted = json.loads(raw_response)
        except Exception:
            submitted = {}

    hits = 0
    for pair in pairs:
        act = (pair.get("activity") or "").strip()
        ans = (pair.get("answer") or "").strip()
        if act and _norm(submitted.get(act, "")) == _norm(ans):
            hits += 1
    score = hits / len(pairs)
    return {
        "is_correct": score == 1.0,
        "score": score,
        "feedback_en": "" if score == 1.0 else f"{hits}/{len(pairs)} pairs matched.",
        "feedback_ar": "" if score == 1.0 else f"{hits}/{len(pairs)} مطابقة صحيحة.",
    }


def grade_speaking_sentence_builder(question, raw_response: Any) -> dict:
    """Speaking tasks are not auto-graded synchronously. The student
    practices with the AI tutor (`tutor` app) which stores the
    pronunciation/grammar/confidence scores on `TutorEvaluation`. Here
    we accept any non-empty response as "noted" and let the tutor
    pipeline supply the real score later."""
    noted = bool((raw_response or "").strip()) if isinstance(raw_response, str) else bool(raw_response)
    return {
        "is_correct": noted,
        "score": 1.0 if noted else 0.0,
        "feedback_en": "" if noted else "Open the AI tutor and try saying it out loud.",
        "feedback_ar": "" if noted else "افتح المعلم الذكي وحاول قولها بصوت.",
    }


def grade_question_transform(question, raw_response: Any) -> dict:
    """Validate a statement→question transformation. We check:
      - starts with the target question word (How often / When / What / …)
      - contains 'do' or 'does' as the auxiliary in present simple
      - contains the original subject (lower-cased)
      - contains the original base verb (not the 3rd-person form)
    All four signals = is_correct; 3 of 4 = partial credit.
    """
    statement = (question.metadata.get("statement") or "").strip()
    target_qword = (question.metadata.get("target_qword") or "").strip().lower()
    expected = (question.correct_answer or "").strip()
    response = (raw_response or "").strip()
    if not response:
        return {"is_correct": False, "score": 0.0,
                "feedback_en": "Please write the question.",
                "feedback_ar": "اكتب السؤال من فضلك."}

    response_low = response.lower()
    # 1. Question word
    ok_qword = response_low.startswith(target_qword) if target_qword else True
    # 2. Auxiliary
    ok_aux = bool(re.search(r"\b(does|do)\b", response_low))
    # 3. Subject extraction from the source statement (simple heuristic:
    #    first word that isn't a question word).
    src_words = statement.split()
    subject = src_words[0].lower() if src_words else ""
    # Convert 3rd-person pronouns/names appearing as subject — student
    # should keep the same subject in the question.
    ok_subject = subject in response_low if subject else True
    # 4. Base verb — find the verb in the statement (heuristically the
    #    word after the subject), drop the -s if present.
    base_verb = ""
    if len(src_words) >= 2:
        v = src_words[1].strip(",.!?").lower()
        base_verb = v[:-1] if v.endswith("s") and len(v) > 3 else v
    ok_verb = bool(base_verb) and re.search(rf"\b{re.escape(base_verb)}\b", response_low) is not None

    hits = sum([ok_qword, ok_aux, ok_subject, ok_verb])
    score = hits / 4.0
    is_correct = (hits == 4) or (_norm(response) == _norm(expected))
    feedback_en = ""
    if not is_correct:
        missing = []
        if not ok_qword: missing.append(f"start with '{target_qword}'")
        if not ok_aux: missing.append("use 'do' or 'does'")
        if not ok_subject: missing.append("keep the original subject")
        if not ok_verb: missing.append("use the base verb (no -s)")
        feedback_en = "Check: " + "; ".join(missing) + "."
    return {
        "is_correct": is_correct,
        "score": 1.0 if is_correct else score,
        "feedback_en": feedback_en,
        "feedback_ar": "" if is_correct else "راجع المكونات الأربعة للسؤال.",
    }


# -------- dispatcher -------------------------------------------------------

GRADERS = {
    "sentence_ordering":          grade_sentence_ordering,
    "frequency_scale":            grade_frequency_scale,
    "table_sentence_builder":     grade_table_sentence_builder,
    "listening_match":            grade_listening_match,
    "speaking_sentence_builder":  grade_speaking_sentence_builder,
    "speaking_prompt":            grade_speaking_sentence_builder,
    "question_transform":         grade_question_transform,
}


def grade_question(question, raw_response: Any) -> dict:
    """Grade one LessonQuestion. Falls back to case-insensitive string
    equality for any type without a custom grader (legacy behaviour)."""
    grader = GRADERS.get(question.question_type)
    if grader is None:
        return _grade_legacy_equality(question, raw_response)
    return grader(question, raw_response)
