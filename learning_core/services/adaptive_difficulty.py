"""Adaptive Difficulty Engine (simplified IRT).

Maintains per-student theta_score on [-3, +3] using a Rasch-style update.
Maps theta to a CEFR level estimate. Updates per-skill mastery from attempts.
"""
from __future__ import annotations

import math
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from learning_core.models import (
    AdaptiveExercise,
    ExerciseAttempt,
    Skill,
    SkillMastery,
    StudentLearningProfile,
)

THETA_MIN = -3.0
THETA_MAX = 3.0
DEFAULT_ALPHA = 0.1
MASTERY_MAX = 100.0
MASTERY_GAIN = 6.0
MASTERY_LOSS = 4.0

# theta → CEFR mapping (rough but stable). C3 is reserved for advanced
# communication beyond C2; reachable only with theta ≥ 2.8.
THETA_TO_CEFR = [
    (-2.5, "A0"),
    (-1.5, "A1"),
    (-0.5, "A2"),
    (0.5, "B1"),
    (1.5, "B2"),
    (2.4, "C1"),
    (2.8, "C2"),
    (3.1, "C3"),
]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def expected_score(theta: float, difficulty: float) -> float:
    """1PL/Rasch logistic: P(correct) = 1 / (1 + exp(-(theta - difficulty)))

    `difficulty` is 0..1 in our schema. We rescale to roughly [-3, +3] so
    the units match theta.
    """
    rescaled_difficulty = (difficulty * 6.0) - 3.0
    return 1.0 / (1.0 + math.exp(-(theta - rescaled_difficulty)))


def cefr_for_theta(theta: float) -> str:
    for upper, level in THETA_TO_CEFR:
        if theta < upper:
            return level
    return "C2"


def cefr_progress(theta: float, current_level: str | None = None) -> dict:
    """Where the learner sits between levels.

    Returns ``{current, next, percent, theta}`` where ``percent`` is the
    progress (0..100) into the current band toward the next level. C3 is
    treated as "no next" — percent stays at 100.

    ``current_level`` is an optional override — when provided (typically
    ``Profile.cefr_level``), it pins the displayed band to the user's
    own profile rather than deriving it from theta. This isolates each
    user's dashboard from theta drift: an A0 learner whose theta has
    momentarily climbed into the A2 band still sees "A0 → A1", with the
    bar pegged at 100% to signal they're ready to graduate.
    """
    levels = list(THETA_TO_CEFR)
    levels.sort(key=lambda x: x[0])

    # When the caller pins the level, use it as the source of truth.
    # Otherwise derive from theta as before.
    pinned = (current_level or "").upper() if current_level else ""
    available_levels = {l for _u, l in levels}
    if pinned and pinned in available_levels:
        current = pinned
        # lower_theta = floor of the pinned band. The floor is the
        # `upper` of the band *before* this one; A0 floors at -3.0.
        idx = next(i for i, (_u, l) in enumerate(levels) if l == current)
        lower_theta = -3.0 if idx == 0 else levels[idx - 1][0]
        next_level = levels[idx + 1][1] if idx + 1 < len(levels) else None
    else:
        # Find the band [lower, upper) that contains theta.
        lower_theta = -3.0
        current = "A0"
        next_level = None
        for upper, lvl in levels:
            if theta < upper:
                current = lvl
                next_idx = levels.index((upper, lvl)) + 1
                if next_idx < len(levels):
                    next_level = levels[next_idx][1]
                break
            lower_theta = upper
        else:
            current = "C2"

    if current == "C3" or next_level is None:
        return {"current": current, "next": None, "percent": 100, "theta": round(theta, 3)}
    upper_theta = next(u for u, l in levels if l == current)
    span = max(upper_theta - lower_theta, 0.001)
    pct = (theta - lower_theta) / span * 100.0
    return {
        "current": current,
        "next": next_level,
        "percent": max(0, min(100, int(round(pct)))),
        "theta": round(theta, 3),
    }


def _ensure_profile(user) -> StudentLearningProfile:
    profile, _ = StudentLearningProfile.objects.get_or_create(user=user)
    return profile


_LEVEL_ORDER = ["A0", "A1", "A2", "B1", "B2", "C1", "C2", "C3"]


def _level_index(level: str) -> int:
    try:
        return _LEVEL_ORDER.index(level or "")
    except ValueError:
        return -1


def update_theta(user, exercise: AdaptiveExercise, attempt: ExerciseAttempt, alpha: float = DEFAULT_ALPHA) -> StudentLearningProfile:
    """Apply a single Rasch update from one attempt. Persists profile."""
    profile = _ensure_profile(user)
    previous_level = profile.current_cefr_level
    expected = expected_score(profile.theta_score, exercise.difficulty_score)
    actual = float(attempt.score) if attempt.score is not None else (1.0 if attempt.is_correct else 0.0)
    new_theta = profile.theta_score + alpha * (actual - expected)
    profile.theta_score = _clamp(new_theta, THETA_MIN, THETA_MAX)
    profile.current_cefr_level = cefr_for_theta(profile.theta_score)
    profile.last_activity_at = timezone.now()
    profile.save(update_fields=["theta_score", "current_cefr_level", "last_activity_at", "updated_at"])

    # Notify on level-up only.
    if (
        previous_level
        and profile.current_cefr_level
        and profile.current_cefr_level != previous_level
        and _level_index(profile.current_cefr_level) > _level_index(previous_level)
    ):
        try:
            from notifications import constants as C
            from notifications.services import NotificationService
            NotificationService().trigger(
                C.LEVEL_IMPROVED,
                user=user,
                payload={
                    "from_level": previous_level,
                    "to_level": profile.current_cefr_level,
                    "cta_url": "/dashboard/",
                    "cta_label": "Keep learning",
                    "dedup_key": f"levelup:{previous_level}->{profile.current_cefr_level}",
                },
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning("level_improved notify failed", exc_info=True)
    return profile


def recommend_next_difficulty(user, target_p: float = 0.7) -> float:
    """Return a difficulty in [0,1] that produces ~target_p success probability
    given the user's current theta. Higher target_p = easier."""
    profile = _ensure_profile(user)
    # Solve theta - rescaled_d = logit(target_p) → rescaled_d = theta - logit(target_p)
    target_p = _clamp(target_p, 0.05, 0.95)
    logit = math.log(target_p / (1.0 - target_p))
    rescaled_d = profile.theta_score - logit
    difficulty = (rescaled_d + 3.0) / 6.0
    return _clamp(difficulty, 0.05, 0.95)


def update_skill_mastery(user, skill: Skill, attempt: ExerciseAttempt) -> SkillMastery:
    mastery, _ = SkillMastery.objects.get_or_create(user=user, skill=skill)
    mastery.attempts_count = (mastery.attempts_count or 0) + 1
    if attempt.is_correct:
        mastery.correct_count += 1
        delta = MASTERY_GAIN
    else:
        mastery.wrong_count += 1
        delta = -MASTERY_LOSS
    mastery.mastery_score = _clamp(mastery.mastery_score + delta, 0.0, MASTERY_MAX)
    mastery.last_practiced_at = timezone.now()
    mastery.save(
        update_fields=[
            "attempts_count",
            "correct_count",
            "wrong_count",
            "mastery_score",
            "last_practiced_at",
            "updated_at",
        ]
    )
    return mastery


def process_attempt(user, exercise: AdaptiveExercise, attempt: ExerciseAttempt) -> dict:
    """Convenience: update theta and mastery in one transaction."""
    with transaction.atomic():
        profile = update_theta(user, exercise, attempt)
        mastery = None
        if exercise.skill_id:
            mastery = update_skill_mastery(user, exercise.skill, attempt)
    return {
        "theta_score": profile.theta_score,
        "cefr_level": profile.current_cefr_level,
        "mastery_score": mastery.mastery_score if mastery else None,
    }


def get_learning_state(user) -> dict:
    profile = _ensure_profile(user)
    masteries: Iterable[SkillMastery] = (
        SkillMastery.objects.filter(user=user).select_related("skill").order_by("-mastery_score")
    )
    masteries_list = list(masteries)
    return {
        "theta_score": round(profile.theta_score, 4),
        "cefr_level": profile.current_cefr_level or cefr_for_theta(profile.theta_score),
        "strongest_skills": [
            {"skill": m.skill.name, "score": m.mastery_score}
            for m in masteries_list[:3]
        ],
        "weakest_skills": [
            {"skill": m.skill.name, "score": m.mastery_score}
            for m in list(reversed(masteries_list))[:3]
        ],
        "recommended_difficulty": round(recommend_next_difficulty(user), 3),
    }
