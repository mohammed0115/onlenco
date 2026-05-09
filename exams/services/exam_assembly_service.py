"""Materialise an Exam from a blueprint by sampling AdaptiveExercise rows.

Public surface:
    assemble_exam(user=None, blueprint=None, *, exam_type=None,
                  cefr_level=None, skill=None, adaptive=False) -> Exam
"""
from __future__ import annotations

import random
from typing import Optional

from django.db import transaction
from django.db.models import QuerySet

from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
)

from ..models import Exam, ExamBlueprint, ExamQuestion
from .. import constants as C
from .exam_blueprint_service import for_signature


def _difficulty_band(label: str) -> tuple[float, float]:
    return {
        "easy":   (0.0, 0.34),
        "medium": (0.34, 0.67),
        "hard":   (0.67, 1.01),
    }.get(label, (0.0, 1.0))


def _attempted_ids(user) -> set:
    if not user:
        return set()
    return set(
        ExerciseAttempt.objects.filter(user=user).values_list("exercise_id", flat=True)
    )


def _pick_in_band(qs: QuerySet, band: tuple[float, float], count: int) -> list[AdaptiveExercise]:
    lo, hi = band
    band_qs = qs.filter(difficulty_score__gte=lo, difficulty_score__lt=hi).order_by("?")
    items = list(band_qs[:count])
    if len(items) < count:
        # Fall back to band-agnostic pick for the shortfall.
        already = {i.id for i in items}
        items += list(qs.exclude(id__in=already).order_by("?")[:count - len(items)])
    return items


def _select_questions(
    blueprint: ExamBlueprint,
    *,
    user=None,
    adaptive: bool = False,
) -> list[AdaptiveExercise]:
    base = AdaptiveExercise.objects.filter(is_active=True)
    if blueprint.cefr_level:
        base = base.filter(cefr_level=blueprint.cefr_level)
    if blueprint.skill:
        base = base.filter(skill__category=blueprint.skill)

    # Optionally avoid items the user has already attempted.
    attempted = _attempted_ids(user)
    if attempted:
        base = base.exclude(id__in=attempted)

    if adaptive and user:
        # Adaptive bias: pull weakness skill first.
        try:
            from learning_core.services.weakness_engine import get_top_weaknesses
            top = get_top_weaknesses(user, limit=2)
            weak_skill_ids = [w.skill_id for w in top if w.skill_id]
            if weak_skill_ids:
                base = base.filter(skill_id__in=weak_skill_ids) | base.exclude(
                    skill_id__in=weak_skill_ids
                )
        except Exception:
            pass

    target_count = max(1, blueprint.total_questions)
    diff_dist = blueprint.difficulty_distribution or {"medium": 1.0}

    out: list[AdaptiveExercise] = []
    for label, ratio in diff_dist.items():
        share = max(1, int(round(ratio * target_count)))
        out += _pick_in_band(base, _difficulty_band(label), share)
        if len(out) >= target_count:
            break

    # Trim / pad to exact target.
    if len(out) > target_count:
        out = out[:target_count]
    if len(out) < target_count:
        already = {i.id for i in out}
        out += list(base.exclude(id__in=already).order_by("?")[:target_count - len(out)])

    random.shuffle(out)
    return out


def assemble_exam(
    *,
    user=None,
    blueprint: Optional[ExamBlueprint] = None,
    exam_type: Optional[str] = None,
    cefr_level: Optional[str] = None,
    skill: str = "",
    adaptive: bool = False,
    title: str | None = None,
) -> Exam:
    if blueprint is None:
        if not (exam_type and cefr_level):
            raise ValueError("Provide a blueprint or (exam_type, cefr_level).")
        blueprint = for_signature(exam_type=exam_type, cefr_level=cefr_level, skill=skill)
        if not blueprint:
            raise ValueError(
                f"No active blueprint for exam_type={exam_type} cefr={cefr_level} skill={skill}"
            )

    questions = _select_questions(blueprint, user=user, adaptive=adaptive)

    with transaction.atomic():
        exam = Exam.objects.create(
            title=title or f"{blueprint.name}",
            blueprint=blueprint,
            exam_type=blueprint.exam_type,
            cefr_level=blueprint.cefr_level,
            skill=blueprint.skill or "",
            total_questions=len(questions),
            duration_minutes=blueprint.duration_minutes,
            is_adaptive=adaptive,
            metadata={"requested_by_user": getattr(user, "id", None)},
        )
        ExamQuestion.objects.bulk_create([
            ExamQuestion(exam=exam, question=q, order=i + 1, points=q.points or 1)
            for i, q in enumerate(questions)
        ])
    return exam
