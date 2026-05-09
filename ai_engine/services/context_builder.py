"""Format retrieved items into LLM-ready prompt context.

Each builder takes the raw retrieval lists and produces a small dict
that can be folded into the system/user message. Keeping this layer
separate means we can later swap prompt formats (chat vs completion,
JSON-mode vs free-form) without touching the retrievers.

Token budget
------------
RAG context that exceeds a few thousand tokens slows the LLM and
inflates cost. Builders truncate aggressively:
  * keep only the top `limit` items
  * trim long fields (questions/answers) to MAX_FIELD_CHARS
  * drop rarely-useful fields (options on errors, metadata blobs)
"""
from __future__ import annotations

from typing import Iterable

MAX_FIELD_CHARS = 280       # roughly one tweet-length sentence
MAX_EXAMPLES_DEFAULT = 5


def _trim(text: str, *, max_chars: int = MAX_FIELD_CHARS) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def build_exercise_generation_context(
    questions: Iterable[dict], *, limit: int = MAX_EXAMPLES_DEFAULT,
) -> dict:
    """Reference questions to imitate when generating a new exercise."""
    items = []
    for q in list(questions)[:limit]:
        items.append({
            "cefr_level": q.get("cefr_level", ""),
            "skill": q.get("skill", ""),
            "question": _trim(q.get("question", "")),
            "options": list(q.get("options") or [])[:6],
            "correct_answer": _trim(q.get("correct_answer", ""), max_chars=80),
            "explanation": _trim(q.get("explanation", "")),
        })
    return {
        "task": "exercise_generation",
        "reference_questions": items,
        "instructions": (
            "Use the reference questions as style + difficulty templates. "
            "Do NOT copy them; write a fresh question that matches the "
            "level and topic."
        ),
    }


def build_error_analysis_context(
    examples: Iterable[dict], *, limit: int = MAX_EXAMPLES_DEFAULT,
) -> dict:
    """Past (wrong-answer → correction) pairs for in-context learning."""
    items = []
    for e in list(examples)[:limit]:
        inp, out = e.get("input") or {}, e.get("output") or {}
        items.append({
            "student_answer": _trim(str(inp.get("student_answer", ""))),
            "correct_answer": _trim(str(inp.get("correct_answer", "")), max_chars=80),
            "error_type":    _trim(str(out.get("error_type", "")), max_chars=40),
            "correction":    _trim(str(out.get("correction", "")), max_chars=80),
            "severity":      out.get("severity"),
            "explanation":   _trim(str(out.get("explanation", ""))),
        })
    return {
        "task": "error_analysis",
        "reference_corrections": items,
        "instructions": (
            "Use the reference corrections as a style guide for the "
            "explanation. Match severity scale and tag conventions."
        ),
    }


def build_answer_explanation_context(
    examples: Iterable[dict], *, limit: int = MAX_EXAMPLES_DEFAULT,
) -> dict:
    """Past (Q + student answer + correct answer → explanation) pairs."""
    items = []
    for e in list(examples)[:limit]:
        inp, out = e.get("input") or {}, e.get("output") or {}
        items.append({
            "question":      _trim(str(inp.get("question", ""))),
            "student_answer":_trim(str(inp.get("student_answer", "")), max_chars=80),
            "correct_answer":_trim(str(inp.get("correct_answer", "")), max_chars=80),
            "explanation":   _trim(str(out.get("explanation", ""))),
        })
    return {
        "task": "answer_explanation",
        "reference_explanations": items,
        "instructions": (
            "Use the reference explanations as a style guide. Be concise "
            "(2–3 short sentences) and CEFR-appropriate."
        ),
    }


def build_tutor_reply_context(
    examples: Iterable[dict],
    weaknesses: Iterable[dict] | None = None,
    *,
    limit: int = MAX_EXAMPLES_DEFAULT,
) -> dict:
    """Past tutor exchanges + the student's current weakness profile."""
    items = []
    for e in list(examples)[:limit]:
        inp, out = e.get("input") or {}, e.get("output") or {}
        items.append({
            "student": _trim(str(inp.get("student_question", ""))),
            "tutor":   _trim(str(out.get("tutor_reply", "")
                                  or out.get("reply", ""))),
        })
    return {
        "task": "tutor_reply",
        "reference_dialogues": items,
        "student_weaknesses": list(weaknesses or [])[:5],
        "instructions": (
            "Reply in the tutor's voice. Address the student's question "
            "using their CEFR level and known weak topics."
        ),
    }


# ---------------------------------------------------------------------------
# One-stop helper — picks the right builder per task type
# ---------------------------------------------------------------------------

def build_for_task(task_type: str, *, items: list[dict],
                   weaknesses: list[dict] | None = None,
                   limit: int = MAX_EXAMPLES_DEFAULT) -> dict:
    if task_type == "exercise_generation":
        return build_exercise_generation_context(items, limit=limit)
    if task_type == "error_analysis":
        return build_error_analysis_context(items, limit=limit)
    if task_type == "answer_explanation":
        return build_answer_explanation_context(items, limit=limit)
    if task_type == "tutor_reply":
        return build_tutor_reply_context(items, weaknesses=weaknesses, limit=limit)
    # Default — return the trimmed items wrapped in a simple envelope.
    return {"task": task_type, "examples": list(items)[:limit]}
