"""Dispatch a (task_type, build) pair to the correct task builder.

Keeping the dispatch table here means callers (the management command
and tests) don't have to know which module owns which task."""
from __future__ import annotations

import logging
from typing import Callable

from django.utils import timezone

from . import _base
from . import (
    answer_dataset_builder,
    cefr_dataset_builder,
    error_dataset_builder,
    exercise_generation_dataset_builder,
    question_dataset_builder,
)
from ..models import DatasetBuild
from .. import constants as C

logger = logging.getLogger(__name__)

BUILDERS: dict[str, Callable[[DatasetBuild], dict]] = {
    C.TASK_ERROR_ANALYSIS:      error_dataset_builder.build,
    C.TASK_CEFR_PREDICTION:     cefr_dataset_builder.build,
    C.TASK_EXERCISE_GENERATION: exercise_generation_dataset_builder.build,
    C.TASK_ANSWER_EXPLANATION:  answer_dataset_builder.build,
    C.TASK_TUTOR_REPLY:         question_dataset_builder.build,
}


def run(build: DatasetBuild, *, min_quality: int = 60) -> dict:
    """Mark the build running, dispatch to the right task builder,
    and finalise. Returns the per-task stats dict for the operator."""
    build.status = C.BUILD_RUNNING
    build.save(update_fields=["status"])
    fn = BUILDERS.get(build.task_type)
    if fn is None:
        return _finish_failed(build, f"Unknown task_type: {build.task_type}")
    try:
        stats = fn(build, min_quality=min_quality)
    except Exception as e:
        logger.exception("dataset build crashed")
        return _finish_failed(build, str(e))
    _base.finalise_build(build, status=C.BUILD_COMPLETED)
    return stats


def _finish_failed(build: DatasetBuild, msg: str) -> dict:
    _base.finalise_build(build, status=C.BUILD_FAILED, error_message=msg)
    return {"accepted": 0, "rejected": 0, "duplicates": 0,
            "private_data_hits": 0, "low_quality_dropped": 0,
            "error": msg}
