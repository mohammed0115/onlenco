"""Builder for the `error_analysis` task.

Input  : student answer + correct answer + question
Output : error_type, grammar_topic, correction, severity, explanation

Source: `learning_core.UserError`. Each row is already a teacher-style
correction; we just have to rejoin it with the question (when available
via the metadata's question_id) and emit the training pair.
"""
from __future__ import annotations

import logging
from typing import Iterable

from learning_core.models import AdaptiveExercise, UserError

from . import _base
from ..models import DatasetBuild
from .. import constants as C

logger = logging.getLogger(__name__)


def _question_lookup(question_ids: list[int]) -> dict[int, AdaptiveExercise]:
    if not question_ids:
        return {}
    rows = AdaptiveExercise.objects.filter(id__in=question_ids).only(
        "id", "question", "correct_answer", "cefr_level", "skill",
    )
    return {r.id: r for r in rows}


def _iter_user_errors(filters: dict) -> Iterable[dict]:
    qs = UserError.objects.exclude(original_text="").exclude(corrected_text="")
    if filters.get("min_severity"):
        qs = qs.filter(severity__gte=int(filters["min_severity"]))
    if filters.get("source_type"):
        qs = qs.filter(source_type=filters["source_type"])
    qs = qs.select_related("skill", "grammar_topic")

    # Pre-fetch related questions once so we don't N+1.
    candidates = list(qs.iterator(chunk_size=500))
    qids = [
        int(c.metadata.get("question_id"))
        for c in candidates
        if isinstance(c.metadata, dict) and c.metadata.get("question_id")
    ]
    question_lookup = _question_lookup(qids)

    for err in candidates:
        question_text = ""
        cefr_level = ""
        skill_str = ""
        qid = (err.metadata or {}).get("question_id") if err.metadata else None
        q = question_lookup.get(int(qid)) if qid else None
        if q is not None:
            question_text = q.question or ""
            cefr_level = q.cefr_level or ""
            skill_str = q.skill.category if q.skill_id and q.skill else ""
        else:
            cefr_level = ""
            skill_str = err.skill.category if err.skill_id and err.skill else ""

        topic_name = ""
        if err.grammar_topic_id and err.grammar_topic:
            topic_name = err.grammar_topic.name

        yield {
            "task_type": C.TASK_ERROR_ANALYSIS,
            "source_type": "UserError",
            "source_id": err.id,
            "cefr_level": cefr_level,
            "skill": skill_str,
            "quality_score": int((err.ai_confidence or 0) * 100),
            "language": "en",
            "input": {
                "question": question_text,
                "student_answer": err.original_text,
                "correct_answer": err.corrected_text,
            },
            "output": {
                "error_type": err.error_type or "",
                "grammar_topic": topic_name,
                "correction": err.corrected_text,
                "severity": int(err.severity or 0),
                "explanation": err.explanation or "",
            },
        }


def build(build_row: DatasetBuild, *, min_quality: int = 0) -> dict:
    return _base.persist_stream(
        build_row, _iter_user_errors(build_row.filters or {}),
        min_quality=min_quality, require_cefr=False,
    )
