"""Builder for the `exercise_generation` task.

Input  : CEFR level + skill + topic + difficulty
Output : question, options, answer, explanation

Sources we pull from:
  * `learning_core.AdaptiveExercise` (reviewed + approved questions)
  * `question_factory.GeneratedQuestion` (`approved_for_training=True`)

Only items that have explanations are emitted — without an explanation
the model has nothing to learn beyond the answer string."""
from __future__ import annotations

import logging
from typing import Iterable

from learning_core.models import AdaptiveExercise
from question_factory.models import GeneratedQuestion

from . import _base
from ..models import DatasetBuild
from .. import constants as C

logger = logging.getLogger(__name__)


def _from_adaptive_exercise(filters: dict) -> Iterable[dict]:
    qs = AdaptiveExercise.objects.filter(is_active=True, is_reviewed=True)
    if filters.get("cefr_level"):
        qs = qs.filter(cefr_level=filters["cefr_level"])
    if filters.get("min_quality_score") is not None:
        qs = qs.filter(quality_score__gte=int(filters["min_quality_score"]))
    qs = qs.exclude(question="").exclude(correct_answer="")
    for ex in qs.iterator(chunk_size=500):
        topic = ex.topic.name if ex.topic_id and ex.topic else ""
        skill = ex.skill.category if ex.skill_id and ex.skill else ""
        yield {
            "task_type": C.TASK_EXERCISE_GENERATION,
            "source_type": "AdaptiveExercise",
            "source_id": ex.id,
            "cefr_level": ex.cefr_level or "",
            "skill": skill,
            "quality_score": int(ex.quality_score or 0),
            "language": ex.language or "en",
            "input": {
                "cefr_level": ex.cefr_level or "",
                "skill": skill,
                "topic": topic,
                "difficulty": float(ex.difficulty_score or 0.5),
                "question_type": ex.question_type,
            },
            "output": {
                "question": ex.question,
                "options": list(ex.options or []),
                "correct_answer": ex.correct_answer,
                "explanation": ex.explanation or "",
            },
        }


def _from_generated_questions(filters: dict) -> Iterable[dict]:
    qs = GeneratedQuestion.objects.filter(
        is_active=True, approved_for_training=True,
    )
    if filters.get("cefr_level"):
        qs = qs.filter(cefr_level=filters["cefr_level"])
    if filters.get("min_quality_score") is not None:
        qs = qs.filter(quality_score__gte=int(filters["min_quality_score"]))
    qs = qs.exclude(question_text="").exclude(correct_answer="")
    for gq in qs.iterator(chunk_size=500):
        yield {
            "task_type": C.TASK_EXERCISE_GENERATION,
            "source_type": "GeneratedQuestion",
            "source_id": gq.id,
            "cefr_level": gq.cefr_level or "",
            "skill": gq.skill or "",
            "quality_score": int(gq.quality_score or 0),
            "language": "en",
            "input": {
                "cefr_level": gq.cefr_level or "",
                "skill": gq.skill or "",
                "topic": gq.vocabulary_topic or (
                    gq.grammar_topic.name if gq.grammar_topic_id and gq.grammar_topic else ""
                ),
                "difficulty": float(gq.difficulty_score or 0.5),
                "question_type": gq.question_type,
            },
            "output": {
                "question": gq.question_text,
                "options": list(gq.options or []),
                "correct_answer": gq.correct_answer,
                "explanation": gq.explanation or "",
            },
        }


def build(build_row: DatasetBuild, *, min_quality: int = 60) -> dict:
    candidates = list(_from_adaptive_exercise(build_row.filters or {}))
    candidates += list(_from_generated_questions(build_row.filters or {}))
    return _base.persist_stream(
        build_row, iter(candidates),
        min_quality=min_quality, require_cefr=False,
    )
