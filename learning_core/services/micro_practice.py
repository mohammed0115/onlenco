"""Micro-practice: instantly hand a learner 3 quick exercises.

Public API:
    micro_practice(user, count=3) -> list[AdaptiveExercise]

How it picks:
    1. If the user has a top weakness, prefer an unattempted exercise on
       that skill/topic at the recommended difficulty.
    2. Else fall back to any unattempted exercise at the user's CEFR
       band that they haven't seen recently.
    3. Else generate a fresh batch via `exercise_generator` and return
       the first `count` items.

The function never raises and never returns an empty list when the
exercise generator succeeds.
"""
from __future__ import annotations

import logging
from typing import List

from django.utils import timezone

from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    StudentLearningProfile,
    UserWeakness,
)
from learning_core.services.adaptive_difficulty import recommend_next_difficulty
from learning_core.services.weakness_engine import get_top_weaknesses

logger = logging.getLogger(__name__)


def _attempted_ids(user) -> set:
    return set(
        ExerciseAttempt.objects
        .filter(user=user)
        .values_list("exercise_id", flat=True)
    )


def _profile_level(user) -> str:
    prof = StudentLearningProfile.objects.filter(user=user).first()
    return getattr(prof, "current_cefr_level", "") or "A2"


def _pick_for_weakness(user, w: UserWeakness, target_difficulty: float, exclude: set) -> List[AdaptiveExercise]:
    qs = AdaptiveExercise.objects.exclude(id__in=exclude)
    if w.skill_id:
        qs = qs.filter(skill_id=w.skill_id)
    if w.grammar_topic_id:
        qs = qs.filter(topic_id=w.grammar_topic_id)
    # Prefer items within ±0.25 of target difficulty.
    near = qs.filter(
        difficulty_score__gte=target_difficulty - 0.25,
        difficulty_score__lte=target_difficulty + 0.25,
    )
    return list(near[:5]) or list(qs[:5])


def _pick_for_level(user, level: str, exclude: set) -> List[AdaptiveExercise]:
    """Random sample at the user's CEFR level, falling back to ±1 band so
    a learner with no exact-level content still gets practice."""
    levels = ["A0", "A1", "A2", "B1", "B2", "C1", "C2", "C3"]
    try:
        i = levels.index(level)
    except ValueError:
        i = 2  # default A2
    bands = [levels[i]]
    if i > 0:
        bands.append(levels[i - 1])
    if i + 1 < len(levels):
        bands.append(levels[i + 1])
    qs = (
        AdaptiveExercise.objects
        .exclude(id__in=exclude)
        .filter(cefr_level__in=bands)
        .order_by("?")
    )
    return list(qs[:10])


def micro_practice(user, count: int = 3) -> List[AdaptiveExercise]:
    """Return up to `count` ready-to-attempt exercises."""
    count = max(1, min(int(count or 3), 10))
    attempted = _attempted_ids(user)
    target = recommend_next_difficulty(user, target_p=0.7)
    out: List[AdaptiveExercise] = []

    # 1. Weakness-driven
    for w in get_top_weaknesses(user, limit=2):
        for ex in _pick_for_weakness(user, w, target, attempted):
            if ex.id in attempted:
                continue
            out.append(ex)
            attempted.add(ex.id)
            if len(out) >= count:
                return out

    # 2. Level-band fallback
    if len(out) < count:
        for ex in _pick_for_level(user, _profile_level(user), attempted):
            out.append(ex)
            attempted.add(ex.id)
            if len(out) >= count:
                return out

    # 3. Generate a fresh batch on demand
    if len(out) < count:
        try:
            from learning_core.services.exercise_generator import generate_personalized_exercises
            fresh = generate_personalized_exercises(user, count_per_weakness=count)
            for ex in fresh or []:
                if ex.id in attempted:
                    continue
                out.append(ex)
                attempted.add(ex.id)
                if len(out) >= count:
                    return out
        except Exception as e:
            logger.warning("micro_practice: generator fallback failed: %s", e)

    return out[:count]
