"""Question-based dynamic placement scoring.

The dynamic placement flow selects real `PlacementQuestion` rows, so scoring
must evaluate each persisted `PlacementAttemptQuestion` and then derive the
final placement result from those scored rows.
"""
from __future__ import annotations

import logging
import re
from typing import Callable

from django.conf import settings
from django.utils import timezone

from placement.models import PlacementAttempt, PlacementAttemptQuestion
from placement.services._assessor import assess as default_assess


logger = logging.getLogger(__name__)


LEVELS = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]
DIMENSION_FIELDS = (
    "skill_score",
    "grammar_score",
    "vocabulary_score",
    "fluency_score",
    "pronunciation_score",
)


def build_dynamic_assessment_payload(attempt: PlacementAttempt) -> dict:
    """Build the structured payload sent to the assessor.

    Includes all selected questions, metadata, and the user's submitted answer.
    The same payload is also used by deterministic fallback scoring and
    diagnostic profile creation.
    """
    items = []
    qs = (
        attempt.questions.select_related("question")
        .order_by("section", "order", "id")
    )
    for aq in qs:
        q = aq.question
        answer = aq.user_answer_text if aq.section == "written" else aq.transcript
        items.append({
            "attempt_question_id": aq.id,
            "question_id": q.id,
            "code": q.code,
            "section": aq.section,
            "order": aq.order,
            "question_text": q.question_text,
            "skill": q.skill,
            "topic": q.topic,
            "difficulty_score": float(q.difficulty_score or 0.5),
            "expected_answer_type": q.expected_answer_type,
            "options": list(q.options or []),
            "scoring_rubric": dict(q.scoring_rubric or {}),
            "user_answer_text": (aq.user_answer_text or "").strip(),
            "transcript": (aq.transcript or "").strip(),
            "answer": (answer or "").strip(),
        })
    return {
        "mode": "dynamic",
        "attempt_id": attempt.id,
        "items": items,
    }


def score_placement_attempt(
    attempt: PlacementAttempt,
    *,
    assessor: Callable[[dict], dict] = default_assess,
) -> dict:
    """Score a dynamic placement attempt and persist every question score."""
    payload = build_dynamic_assessment_payload(attempt)
    fallback = heuristic_dynamic_assessment(payload)

    result = fallback
    if assessor is not default_assess or settings.AI_API_KEY:
        try:
            result = _normalise_assessment(assessor(payload), fallback)
        except Exception:
            logger.exception("dynamic placement assessor failed; using fallback")
            result = fallback

    question_scores = result["question_scores"]
    _persist_question_scores(attempt, question_scores)

    result["transcript"] = _transcript_for_storage(payload, question_scores)
    result["diagnostic_answers"] = payload
    result["recommended_cefr_level"] = result["level"]
    return result


def heuristic_dynamic_assessment(payload: dict) -> dict:
    """Deterministic question-based scoring for dynamic attempts.

    This is intentionally conservative. It uses all selected questions and
    gives reliable onboarding output when AI scoring is unavailable, while
    marking pronunciation as unavailable instead of inventing it.
    """
    scored = [_score_item(item) for item in (payload.get("items") or [])]
    return _result_from_question_rows(
        scored,
        feedback=(
            "Auto-scored from the dynamic placement question set. "
            "Pronunciation scoring is not available yet, so speaking was "
            "graded from the transcript."
        ),
    )


def _score_item(item: dict) -> dict:
    answer = (item.get("answer") or "").strip()
    if item.get("section") == "speaking":
        return _score_speaking_item(item, answer)
    return _score_written_item(item, answer)


def _score_written_item(item: dict, answer: str) -> dict:
    if not answer:
        return _empty_result(item, "No written answer was provided.")

    stats = _text_stats(answer)
    expected = item.get("expected_answer_type") or ""

    if expected == "mcq":
        from placement.services.answer_key import is_answer_correct
        correct = is_answer_correct(
            answer, options=item.get("options"),
            rubric=item.get("scoring_rubric"), expected_type="mcq",
        )
        if correct is None:
            # Legacy options without an answer key — fall back to validity.
            valid = any(
                (o.get("text") if isinstance(o, dict) else o) == answer
                for o in (item.get("options") or [])
            )
            base = 60 if valid else 10
            notes = ["MCQ answer key is not present; scored as answer validity."]
        else:
            base = 100 if correct else 0
            notes = ["MCQ graded against the stored answer key."]
        components = {
            "grammar": base, "spelling": base, "vocabulary": base,
            "sentence_structure": base, "clarity": base, "task_completion": base,
        }
    else:
        target_words, target_sentences = _targets_for_item(item)
        task_completion = _coverage_score(
            stats["word_count"], stats["sentence_count"], target_words, target_sentences
        )
        components = {
            "grammar": _grammar_score(answer, stats, target_sentences),
            "spelling": _spelling_score(stats),
            "vocabulary": _vocabulary_score(stats, target_words),
            "sentence_structure": _sentence_structure_score(stats, target_sentences),
            "clarity": _clarity_score(stats, task_completion),
            "task_completion": task_completion,
        }
        notes = []

    score = _avg_int(list(components.values()))
    return _item_result(
        item,
        score=score,
        skill_score=score,
        grammar_score=components["grammar"],
        vocabulary_score=components["vocabulary"],
        fluency_score=None,
        pronunciation_score=None,
        feedback=_feedback_for_score(score, "written response"),
        error_analysis={
            "source": "dynamic_placement_rule_based",
            "rubric": "written",
            "components": components,
            "notes": notes,
            "text_stats": stats,
            "pronunciation": _pronunciation_unavailable("written_not_applicable"),
        },
    )


def _score_speaking_item(item: dict, transcript: str) -> dict:
    if not transcript:
        row = _empty_result(item, "No speaking transcript was provided.")
        row["fluency_score"] = 0
        row["error_analysis"]["pronunciation"] = _pronunciation_unavailable("no_audio_pronunciation_scorer")
        row["error_analysis"]["fluency"] = {"available": True, "method": "transcript_based"}
        return row

    stats = _text_stats(transcript)
    target_words, target_sentences = _targets_for_item(item)
    transcript_completeness = _coverage_score(
        stats["word_count"], stats["sentence_count"], target_words, target_sentences
    )
    components = {
        "transcript_completeness": transcript_completeness,
        "grammar": _grammar_score(transcript, stats, target_sentences),
        "vocabulary": _vocabulary_score(stats, target_words),
        "clarity": _clarity_score(stats, transcript_completeness),
        "fluency": _fluency_score(stats, target_words),
    }
    score = _avg_int(list(components.values()))
    return _item_result(
        item,
        score=score,
        skill_score=score,
        grammar_score=components["grammar"],
        vocabulary_score=components["vocabulary"],
        fluency_score=components["fluency"],
        pronunciation_score=None,
        feedback=_feedback_for_score(score, "spoken response"),
        error_analysis={
            "source": "dynamic_placement_rule_based",
            "rubric": "speaking_transcript",
            "components": components,
            "text_stats": stats,
            "fluency": {"available": True, "method": "transcript_based"},
            "pronunciation": _pronunciation_unavailable("no_audio_pronunciation_scorer"),
        },
    )


def _empty_result(item: dict, feedback: str) -> dict:
    stats = _text_stats("")
    return _item_result(
        item,
        score=0,
        skill_score=0,
        grammar_score=0,
        vocabulary_score=0,
        fluency_score=None,
        pronunciation_score=None,
        feedback=feedback,
        error_analysis={
            "source": "dynamic_placement_rule_based",
            "components": {},
            "text_stats": stats,
            "pronunciation": _pronunciation_unavailable("no_response"),
        },
    )


def _item_result(
    item: dict,
    *,
    score: int,
    skill_score: int,
    grammar_score: int,
    vocabulary_score: int,
    fluency_score: int | None,
    pronunciation_score: int | None,
    feedback: str,
    error_analysis: dict,
) -> dict:
    return {
        "attempt_question_id": item["attempt_question_id"],
        "section": item["section"],
        "score": _clamp_score(score, 0),
        "skill_score": _clamp_score(skill_score, 0),
        "grammar_score": _clamp_score(grammar_score, 0),
        "vocabulary_score": _clamp_score(vocabulary_score, 0),
        "fluency_score": _clamp_optional(fluency_score),
        "pronunciation_score": None,
        "feedback": feedback,
        "error_analysis": {
            "code": item.get("code", ""),
            "skill": item.get("skill", ""),
            "topic": item.get("topic", ""),
            "expected_answer_type": item.get("expected_answer_type", ""),
            "difficulty_score": item.get("difficulty_score", 0.5),
            **(error_analysis or {}),
        },
    }


def _text_stats(text: str) -> dict:
    words = re.findall(r"[A-Za-z']+", text or "")
    sentences = [s for s in re.split(r"[.!?]+", text or "") if s.strip()]
    unique = {w.lower() for w in words}
    suspicious = [
        w for w in words
        if len(w) > 2 and (re.search(r"([A-Za-z])\1\1", w) or not re.fullmatch(r"[A-Za-z']+", w))
    ]
    fillers = [w for w in words if w.lower() in {"um", "uh", "erm", "like"}]
    avg_word_len = sum(len(w) for w in words) / len(words) if words else 0.0
    return {
        "word_count": len(words),
        "sentence_count": len(sentences),
        "unique_word_count": len(unique),
        "unique_ratio": round(len(unique) / len(words), 3) if words else 0.0,
        "avg_word_length": round(avg_word_len, 2),
        "suspicious_word_count": len(suspicious),
        "filler_count": len(fillers),
        "has_sentence_punctuation": bool(re.search(r"[.!?]", text or "")),
    }


def _targets_for_item(item: dict) -> tuple[int, int]:
    expected = item.get("expected_answer_type") or ""
    difficulty = float(item.get("difficulty_score") or 0.5)
    if expected == "voice":
        return max(18, int(18 + difficulty * 45)), 2
    if expected == "paragraph":
        return max(35, int(30 + difficulty * 70)), 3
    if expected == "sentence":
        return max(8, int(7 + difficulty * 18)), 1
    if expected == "short_text":
        return max(5, int(5 + difficulty * 14)), 1
    return 8, 1


def _coverage_score(word_count: int, sentence_count: int,
                    target_words: int, target_sentences: int) -> int:
    word_part = min(word_count / max(target_words, 1), 1.0) * 70
    sentence_part = min(sentence_count / max(target_sentences, 1), 1.0) * 20
    completion_bonus = 10 if word_count else 0
    return _clamp_score(round(word_part + sentence_part + completion_bonus), 0)


def _grammar_score(text: str, stats: dict, target_sentences: int) -> int:
    if not stats["word_count"]:
        return 0
    score = 42
    score += min(stats["word_count"], 30)
    score += min(stats["sentence_count"] / max(target_sentences, 1), 1.0) * 15
    score += 8 if stats["has_sentence_punctuation"] else 0
    if re.search(r"\bi\b", text):
        score -= 8
    if re.search(r"\b(he|she|it)\s+(go|have|do)\b", text, flags=re.I):
        score -= 10
    if re.search(r"\b(yesterday|last)\b.*\b(go|eat|see|come)\b", text, flags=re.I):
        score -= 8
    return _clamp_score(round(score), 0)


def _spelling_score(stats: dict) -> int:
    if not stats["word_count"]:
        return 0
    suspicious_ratio = stats["suspicious_word_count"] / max(stats["word_count"], 1)
    return _clamp_score(round(100 - suspicious_ratio * 100), 0)


def _vocabulary_score(stats: dict, target_words: int) -> int:
    if not stats["word_count"]:
        return 0
    breadth = min(stats["unique_word_count"] / max(target_words, 1), 1.0) * 55
    variety = stats["unique_ratio"] * 25
    range_bonus = min(stats["avg_word_length"] / 8.0, 1.0) * 20
    return _clamp_score(round(breadth + variety + range_bonus), 0)


def _sentence_structure_score(stats: dict, target_sentences: int) -> int:
    if not stats["word_count"]:
        return 0
    sentence_part = min(stats["sentence_count"] / max(target_sentences, 1), 1.0) * 45
    length_part = min(stats["word_count"] / max(target_sentences * 8, 1), 1.0) * 35
    punctuation = 20 if stats["has_sentence_punctuation"] else 8
    return _clamp_score(round(sentence_part + length_part + punctuation), 0)


def _clarity_score(stats: dict, task_completion: int) -> int:
    if not stats["word_count"]:
        return 0
    base = (task_completion * 0.65) + (_spelling_score(stats) * 0.2)
    base += 15 if stats["sentence_count"] else 0
    return _clamp_score(round(base), 0)


def _fluency_score(stats: dict, target_words: int) -> int:
    if not stats["word_count"]:
        return 0
    flow = min(stats["word_count"] / max(target_words, 1), 1.0) * 55
    sentence_flow = min(stats["sentence_count"] / 2, 1.0) * 25
    filler_penalty = min(stats["filler_count"] * 8, 25)
    return _clamp_score(round(flow + sentence_flow + 20 - filler_penalty), 0)


def _result_from_question_rows(scored: list[dict], *, feedback: str) -> dict:
    written_score = _avg_int([s["score"] for s in scored if s["section"] == "written"])
    speaking_score = _avg_int([s["score"] for s in scored if s["section"] == "speaking"])
    grammar_score = _avg_optional([s.get("grammar_score") for s in scored])
    vocabulary_score = _avg_optional([s.get("vocabulary_score") for s in scored])
    fluency_score = _avg_optional([
        s.get("fluency_score") for s in scored if s["section"] == "speaking"
    ])
    pronunciation_score = _avg_optional([
        s.get("pronunciation_score") for s in scored if s["section"] == "speaking"
    ])
    overall_score = _avg_int([written_score, speaking_score])
    return {
        "level": _level_for_score(overall_score),
        "written_score": written_score,
        "speaking_score": speaking_score,
        "grammar_score": grammar_score,
        "vocabulary_score": vocabulary_score,
        "fluency_score": fluency_score,
        "pronunciation_score": pronunciation_score,
        "overall_score": overall_score,
        "feedback": feedback,
        "question_scores": {
            str(row["attempt_question_id"]): row
            for row in scored
        },
        "pronunciation_available": pronunciation_score is not None,
    }


def _normalise_assessment(raw: dict, fallback: dict) -> dict:
    raw = raw or {}
    question_scores = _normalise_question_scores(raw.get("question_scores"), fallback["question_scores"])
    result = _result_from_question_rows(
        list(question_scores.values()),
        feedback=(raw.get("feedback") or fallback["feedback"] or "").strip(),
    )
    return {
        **result,
        "question_scores": question_scores,
    }


def _normalise_question_scores(raw_scores, fallback_scores: dict) -> dict:
    source = {}
    if isinstance(raw_scores, list):
        for row in raw_scores:
            if isinstance(row, dict) and row.get("attempt_question_id") is not None:
                source[str(row["attempt_question_id"])] = row
    elif isinstance(raw_scores, dict):
        for key, row in raw_scores.items():
            if isinstance(row, dict):
                source[str(key)] = row

    normalised = {}
    for key, fallback in fallback_scores.items():
        row = source.get(str(key)) or {}
        merged = _normalise_question_row(row, fallback)
        normalised[str(key)] = merged
    return normalised


def _normalise_question_row(row: dict, fallback: dict) -> dict:
    score = _clamp_score(row.get("score"), fallback["score"])
    skill_score = _clamp_score(row.get("skill_score"), row.get("score", fallback["skill_score"]))
    grammar_score = _clamp_score(row.get("grammar_score"), fallback["grammar_score"])
    vocabulary_score = _clamp_score(
        row.get("vocabulary_score", row.get("vocab_score")),
        fallback["vocabulary_score"],
    )
    fluency_score = _clamp_optional(row.get("fluency_score"))
    if fluency_score is None:
        fluency_score = fallback.get("fluency_score")
    error_analysis = {
        **(fallback.get("error_analysis") or {}),
        **(row.get("error_analysis") or {}),
    }
    error_analysis["pronunciation"] = _pronunciation_unavailable("no_audio_pronunciation_scorer")
    return {
        **fallback,
        "score": score,
        "skill_score": skill_score,
        "grammar_score": grammar_score,
        "vocabulary_score": vocabulary_score,
        "fluency_score": _clamp_optional(fluency_score),
        "pronunciation_score": None,
        "feedback": (row.get("feedback") or fallback.get("feedback") or "").strip(),
        "error_analysis": error_analysis,
    }


def _persist_question_scores(attempt: PlacementAttempt, question_scores: dict) -> None:
    rows = []
    completed_at = timezone.now()
    for aq in attempt.questions.all():
        row = question_scores.get(str(aq.id)) or question_scores.get(aq.id)
        if not row:
            row = _empty_result({
                "attempt_question_id": aq.id,
                "section": aq.section,
                "code": aq.question.code if aq.question_id else "",
                "skill": aq.question.skill if aq.question_id else "",
                "topic": aq.question.topic if aq.question_id else "",
                "expected_answer_type": aq.question.expected_answer_type if aq.question_id else "",
                "difficulty_score": aq.question.difficulty_score if aq.question_id else 0.5,
            }, "No score was produced for this question.")
        aq.score = row["score"]
        aq.skill_score = row.get("skill_score")
        aq.grammar_score = row.get("grammar_score")
        aq.vocabulary_score = row.get("vocabulary_score")
        aq.fluency_score = row.get("fluency_score")
        aq.pronunciation_score = None
        aq.feedback = row.get("feedback", "")
        aq.error_analysis = row.get("error_analysis", {})
        aq.completed_at = completed_at
        rows.append(aq)
    if rows:
        PlacementAttemptQuestion.objects.bulk_update(
            rows,
            [
                "score", "skill_score", "grammar_score", "vocabulary_score",
                "fluency_score", "pronunciation_score", "feedback",
                "error_analysis", "completed_at",
            ],
        )


def _transcript_for_storage(payload: dict, question_scores: dict) -> dict:
    sections = {"written": [], "speaking": []}
    for item in payload.get("items") or []:
        score = question_scores.get(str(item["attempt_question_id"])) or {}
        sections[item["section"]].append({
            "attempt_question_id": item["attempt_question_id"],
            "code": item["code"],
            "question": item["question_text"],
            "answer": item["answer"],
            "skill": item["skill"],
            "topic": item["topic"],
            "expected_answer_type": item["expected_answer_type"],
            "difficulty_score": item["difficulty_score"],
            "score": score.get("score"),
            "skill_score": score.get("skill_score"),
            "grammar_score": score.get("grammar_score"),
            "vocabulary_score": score.get("vocabulary_score"),
            "fluency_score": score.get("fluency_score"),
            "pronunciation_score": score.get("pronunciation_score"),
            "pronunciation_available": score.get("pronunciation_score") is not None,
        })
    return {"mode": "dynamic", **sections}


def _feedback_for_score(score: int, area: str) -> str:
    if score >= 76:
        return f"Strong {area}."
    if score >= 46:
        return f"Developing {area}; add accuracy and detail for a higher score."
    return f"Limited {area}; try a fuller and clearer answer next time."


def _pronunciation_unavailable(reason: str) -> dict:
    return {
        "available": False,
        "reason": reason,
        "message": "Pronunciation scoring is unavailable; transcript-based speaking scoring was used.",
    }


def _avg_int(values) -> int:
    nums = [int(v) for v in values if v is not None]
    if not nums:
        return 0
    return round(sum(nums) / len(nums))


def _avg_optional(values) -> int | None:
    nums = [int(v) for v in values if v is not None]
    if not nums:
        return None
    return round(sum(nums) / len(nums))


def _clamp_score(value, default: int) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def _clamp_optional(value) -> int | None:
    if value is None:
        return None
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def _level_for_score(score: int) -> str:
    score = _clamp_score(score, 0)
    if score <= 15:
        return "A0"
    if score <= 30:
        return "A1"
    if score <= 45:
        return "A2"
    if score <= 60:
        return "B1"
    if score <= 75:
        return "B2"
    if score <= 90:
        return "C1"
    return "C2"
