"""Builder for the `answer_explanation` task.

Input  : question + student answer + correct answer
Output : personalised explanation

Source: `exams.ExamAnswer` rows that carry a non-empty feedback /
explanation. Only graded attempts are eligible."""
from __future__ import annotations

import logging
from typing import Iterable

from exams.models import ExamAnswer

from . import _base
from ..models import DatasetBuild
from .. import constants as C

logger = logging.getLogger(__name__)


def _iter_exam_answers(filters: dict) -> Iterable[dict]:
    qs = (
        ExamAnswer.objects
        .exclude(user_answer="")
        .select_related("question", "attempt")
    )
    if filters.get("only_correct") is True:
        qs = qs.filter(is_correct=True)
    if filters.get("only_wrong") is True:
        qs = qs.filter(is_correct=False)

    for ans in qs.iterator(chunk_size=500):
        # Prefer the per-answer feedback the scoring service stamped;
        # fall back to the question's static explanation if available.
        explanation = ans.feedback or ans.question.explanation or ""
        if not explanation.strip():
            continue
        yield {
            "task_type": C.TASK_ANSWER_EXPLANATION,
            "source_type": "ExamAnswer",
            "source_id": ans.id,
            "cefr_level": ans.question.cefr_level or "",
            "skill": (ans.question.skill.category
                      if ans.question.skill_id and ans.question.skill else ""),
            "quality_score": 80 if ans.is_correct else 70,
            "language": "en",
            "input": {
                "question": ans.question.question,
                "student_answer": ans.user_answer,
                "correct_answer": ans.question.correct_answer or "",
                "is_correct": bool(ans.is_correct),
            },
            "output": {
                "explanation": explanation,
            },
        }


def build(build_row: DatasetBuild, *, min_quality: int = 0) -> dict:
    return _base.persist_stream(
        build_row, _iter_exam_answers(build_row.filters or {}),
        min_quality=min_quality, require_cefr=False,
    )
