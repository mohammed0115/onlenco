"""Builder for the `cefr_prediction` task.

Input  : student writing or speaking answer
Output : CEFR level, confidence, strengths, weaknesses

Sources:
  * `exams.ExamAnswer` whose question is a writing/speaking prompt and
    whose user has a `StudentLearningProfile.current_cefr_level`.
  * Direct `AdaptiveExercise` writing/speaking samples (model-graded).

The CEFR label is the user's current level at the time of the answer
(persisted denormalised into metadata for replayability)."""
from __future__ import annotations

import logging
from typing import Iterable

from exams.models import ExamAnswer
from learning_core.models import StudentLearningProfile

from . import _base
from ..models import DatasetBuild
from .. import constants as C

logger = logging.getLogger(__name__)

WRITING_TYPES = {"writing_prompt", "short_answer"}
SPEAKING_TYPES = {"speaking_prompt"}


def _profile_levels(user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = StudentLearningProfile.objects.filter(
        user_id__in=user_ids,
    ).values_list("user_id", "current_cefr_level")
    return {uid: lvl for uid, lvl in rows if lvl}


def _iter_exam_answers(filters: dict) -> Iterable[dict]:
    qs = (
        ExamAnswer.objects
        .filter(question__question_type__in=WRITING_TYPES | SPEAKING_TYPES)
        .exclude(user_answer="")
        .select_related("question", "attempt__user")
    )
    candidates = list(qs.iterator(chunk_size=500))
    user_ids = [c.attempt.user_id for c in candidates if c.attempt_id]
    profile_lookup = _profile_levels(user_ids)

    for ans in candidates:
        user_id = ans.attempt.user_id
        cefr = profile_lookup.get(user_id) or (ans.question.cefr_level or "")
        if not cefr:
            continue

        is_speaking = ans.question.question_type in SPEAKING_TYPES
        # Strengths/weaknesses heuristic: derive from is_correct + score.
        score_pct = ans.score / max(1, ans.question.points or 1) * 100
        if score_pct >= 70:
            strengths = ["fluency"] if is_speaking else ["clarity"]
            weaknesses = []
        elif score_pct >= 40:
            strengths = ["effort"]
            weaknesses = ["accuracy"]
        else:
            strengths = []
            weaknesses = ["accuracy", "complexity"]

        yield {
            "task_type": C.TASK_CEFR_PREDICTION,
            "source_type": "ExamAnswer",
            "source_id": ans.id,
            "cefr_level": cefr,
            "skill": "speaking" if is_speaking else "writing",
            "quality_score": int(score_pct),
            "language": "en",
            "input": {
                "text": ans.user_answer,
                "modality": "speaking" if is_speaking else "writing",
            },
            "output": {
                "cefr_level": cefr,
                "confidence": round(score_pct / 100.0, 2),
                "strengths": strengths,
                "weaknesses": weaknesses,
            },
        }


def build(build_row: DatasetBuild, *, min_quality: int = 0) -> dict:
    return _base.persist_stream(
        build_row, _iter_exam_answers(build_row.filters or {}),
        min_quality=min_quality, require_cefr=True,
    )
