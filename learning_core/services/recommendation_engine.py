"""Recommendation Engine.

Produces 3–5 next-best-action recommendations for a student. Combines:
  - active high-priority weaknesses → "practice_skill" / "review_topic"
  - low-mastery skills → "practice_skill"
  - recent inactivity → "continue_lesson" / "ask_tutor"
  - placement age → "retake_placement" after 30 days

Persists as LearningRecommendation. Marks any superseded `pending` rows as
`replaced` so the dashboard only shows the latest set.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from learning_core.models import (
    ExerciseAttempt,
    LearningRecommendation,
    SkillMastery,
    StudentLearningProfile,
    UserWeakness,
)
from learning_core.services.weakness_engine import get_top_weaknesses

MAX_RECS = 5
MIN_RECS = 3
PLACEMENT_RETAKE_DAYS = 30
LOW_MASTERY_THRESHOLD = 40.0
INACTIVITY_DAYS = 7


def _placement_age_days(user) -> int | None:
    try:
        from placement.models import PlacementResult
    except Exception:
        return None
    last = PlacementResult.objects.filter(user=user).order_by("-created_at").first()
    if not last:
        return None
    return (timezone.now() - last.created_at).days


def generate_recommendations(user) -> list[LearningRecommendation]:
    """Compute and persist a fresh set of recommendations for `user`."""
    candidates: list[dict] = []
    seen_keys: set[tuple] = set()

    def _add(*, type_, title, description, priority, skill=None, weakness=None, key=None):
        key = key or (type_, title)
        if key in seen_keys:
            return
        seen_keys.add(key)
        candidates.append(
            {
                "recommendation_type": type_,
                "title": title,
                "description": description,
                "priority": float(priority),
                "related_skill": skill,
                "related_weakness": weakness,
            }
        )

    # 1. From active weaknesses
    weaknesses = get_top_weaknesses(user, limit=5)
    for w in weaknesses:
        topic_label = (
            (w.grammar_topic.name if w.grammar_topic else None)
            or (w.skill.name if w.skill else "general")
        )
        if w.grammar_topic:
            _add(
                type_="review_topic",
                title=f"Review {topic_label}",
                description=(
                    f"You've made repeated mistakes around {topic_label}. "
                    "Spend 5 minutes on a focused review."
                ),
                priority=w.priority_score,
                skill=w.skill,
                weakness=w,
                key=("review_topic", w.id),
            )
        else:
            _add(
                type_="practice_skill",
                title=f"Practice {topic_label}",
                description=(
                    f"Boost your {topic_label.lower()} skills with a few targeted exercises."
                ),
                priority=w.priority_score,
                skill=w.skill,
                weakness=w,
                key=("practice_skill", w.id),
            )

    # 2. From low-mastery skills (skills the user has touched but is weak in)
    low_masteries: Iterable[SkillMastery] = (
        SkillMastery.objects.filter(user=user, mastery_score__lt=LOW_MASTERY_THRESHOLD, attempts_count__gt=0)
        .select_related("skill")
        .order_by("mastery_score")[:3]
    )
    for m in low_masteries:
        _add(
            type_="practice_skill",
            title=f"Strengthen {m.skill.name}",
            description=(
                f"Mastery is currently {m.mastery_score:.0f}%. Aim for a few targeted attempts."
            ),
            priority=max(20.0, 100.0 - m.mastery_score),  # lower mastery → higher priority
            skill=m.skill,
            key=("practice_skill_mastery", m.skill_id),
        )

    # 3. Recent inactivity → ask tutor
    last_attempt = (
        ExerciseAttempt.objects.filter(user=user).order_by("-created_at").first()
    )
    days_since_attempt = (
        (timezone.now() - last_attempt.created_at).days if last_attempt else None
    )
    if days_since_attempt is None or days_since_attempt > INACTIVITY_DAYS:
        _add(
            type_="ask_tutor",
            title="Chat with the AI tutor",
            description=(
                "Get a 5-minute personalized review from the AI tutor — "
                "great for re-engaging."
            ),
            priority=15.0,
            key=("ask_tutor", "inactivity"),
        )

    # 4. Placement retake suggestion if 30+ days old
    age = _placement_age_days(user)
    if age is not None and age >= PLACEMENT_RETAKE_DAYS:
        _add(
            type_="retake_placement",
            title="Retake the placement test",
            description=(
                f"Your placement is {age} days old. Retake it to update your level."
            ),
            priority=10.0,
            key=("retake_placement", "stale"),
        )

    # 5. Always include a fallback "continue_lesson" if we still don't have enough
    if len(candidates) < MIN_RECS:
        _add(
            type_="continue_lesson",
            title="Continue your next lesson",
            description="Pick up the next lesson at your level to keep momentum.",
            priority=5.0,
            key=("continue_lesson", "fallback"),
        )

    # Sort by priority, take top N
    candidates.sort(key=lambda c: c["priority"], reverse=True)
    chosen = candidates[:MAX_RECS]

    with transaction.atomic():
        LearningRecommendation.objects.filter(user=user, status="pending").update(
            status="replaced"
        )
        rows = [
            LearningRecommendation(
                user=user,
                recommendation_type=c["recommendation_type"],
                title=c["title"],
                description=c["description"],
                priority=c["priority"],
                related_skill=c["related_skill"],
                related_weakness=c["related_weakness"],
                status="pending",
            )
            for c in chosen
        ]
        saved = LearningRecommendation.objects.bulk_create(rows)

    return saved
