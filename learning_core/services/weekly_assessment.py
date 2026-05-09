"""Weekly assessment service.

Triggered every `LESSONS_PER_ASSESSMENT` completed lessons. Bundles
existing exercises (or newly generated ones) into a `WeeklyAssessment`
record the student can attempt. After completion, refresh weaknesses +
recommendations.
"""
from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from learning_core.models import (
    AdaptiveExercise,
    LearningRecommendation,
    WeeklyAssessment,
)
from learning_core.services.exercise_generator import generate_personalized_exercises
from learning_core.services.recommendation_engine import generate_recommendations
from learning_core.services.weakness_engine import update_user_weaknesses
from lessons.models import LessonProgress

logger = logging.getLogger(__name__)

LESSONS_PER_ASSESSMENT = 3
EXERCISES_PER_ASSESSMENT = 10
EXERCISES_PER_DAILY = 5


def start_daily_assessment(user):
    """Start (or return today's existing) daily check-in assessment.

    Idempotent within a calendar day: a second call on the same day returns
    the row already created today.
    """
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    existing = (
        WeeklyAssessment.objects.filter(
            user=user, kind="daily", created_at__gte=today_start
        ).order_by("-created_at").first()
    )
    if existing:
        return existing

    with transaction.atomic():
        assessment = WeeklyAssessment.objects.create(
            user=user, kind="daily", status="pending",
        )
        # Bundle 5 exercises: prefer AI-generated targeted ones; fallback to
        # the warm-up template pool.
        exercises = list(
            AdaptiveExercise.objects.filter(attempts__user=user)
            .distinct().order_by("-created_at")[:EXERCISES_PER_DAILY]
        )
        if len(exercises) < EXERCISES_PER_DAILY:
            try:
                generated = generate_personalized_exercises(user, count_per_weakness=2)
                for ex in generated:
                    if ex not in exercises:
                        exercises.append(ex)
                    if len(exercises) >= EXERCISES_PER_DAILY:
                        break
            except Exception as e:
                logger.warning("start_daily_assessment: generation failed: %s", e)
        assessment.exercises.set(exercises[:EXERCISES_PER_DAILY])

    return assessment


def maybe_trigger(user) -> WeeklyAssessment | None:
    """If the student has completed exactly a multiple of N lessons since
    their last assessment, create a new pending one. Returns it (or None)."""
    try:
        completed_count = LessonProgress.objects.filter(
            user=user, completed_at__isnull=False
        ).count()
    except Exception as e:
        logger.warning("weekly_assessment.maybe_trigger: %s", e)
        return None

    if completed_count <= 0 or completed_count % LESSONS_PER_ASSESSMENT != 0:
        return None

    if WeeklyAssessment.objects.filter(
        user=user, triggered_after_lessons_count=completed_count
    ).exists():
        return None

    with transaction.atomic():
        assessment = WeeklyAssessment.objects.create(
            user=user,
            triggered_after_lessons_count=completed_count,
            status="pending",
        )
        # Pull exercises: prefer recent AI-generated; otherwise generate.
        existing = list(
            AdaptiveExercise.objects.filter(
                attempts__user=user
            ).distinct().order_by("-created_at")[:EXERCISES_PER_ASSESSMENT]
        )
        if len(existing) < EXERCISES_PER_ASSESSMENT:
            try:
                generated = generate_personalized_exercises(
                    user, count_per_weakness=2
                )
                for ex in generated:
                    if ex not in existing:
                        existing.append(ex)
                    if len(existing) >= EXERCISES_PER_ASSESSMENT:
                        break
            except Exception as e:
                logger.warning("weekly_assessment: generation failed: %s", e)
        assessment.exercises.set(existing[:EXERCISES_PER_ASSESSMENT])

        # Surface as a recommendation so the dashboard shows it.
        LearningRecommendation.objects.create(
            user=user,
            recommendation_type="weekly_assessment",
            title="Take your weekly assessment",
            description=(
                f"You've completed {completed_count} lessons. "
                "A short quiz will check what you've learned."
            ),
            priority=80.0,
            status="pending",
            metadata={"weekly_assessment_id": assessment.id},
        )

    # Email a clickable link via the central notifications service.
    try:
        from notifications import constants as C
        from notifications.services import NotificationService
        NotificationService().trigger(
            C.WEEKLY_ASSESSMENT_AVAILABLE,
            user=user,
            payload={
                "lessons_count": completed_count,
                "cta_url": f"/dashboard/weekly/{assessment.id}/",
                "cta_label": "Open assessment",
                "dedup_key": f"weekly:{assessment.id}",
            },
        )
    except Exception as e:
        logger.warning("weekly_assessment: notify failed: %s", e)

    return assessment


def complete(assessment: WeeklyAssessment, *, score: float) -> WeeklyAssessment:
    assessment.score = max(0.0, min(100.0, float(score)))
    assessment.status = "completed"
    assessment.completed_at = timezone.now()
    if not assessment.started_at:
        assessment.started_at = assessment.completed_at
    assessment.save(update_fields=["score", "status", "started_at", "completed_at"])

    try:
        update_user_weaknesses(assessment.user)
        generate_recommendations(assessment.user)
    except Exception as e:
        logger.warning("weekly_assessment.complete: refresh failed: %s", e)

    try:
        from notifications import constants as C
        from notifications.services import NotificationService
        NotificationService().trigger(
            C.WEEKLY_ASSESSMENT_RESULT,
            user=assessment.user,
            payload={
                "score": round(assessment.score, 1),
                "cta_url": "/dashboard/",
                "cta_label": "Open dashboard",
                "dedup_key": f"weekly_result:{assessment.id}",
            },
        )
    except Exception as e:
        logger.warning("weekly_assessment.complete: notify failed: %s", e)

    return assessment
