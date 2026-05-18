"""Behavioral analytics — engagement_score + churn_risk_score.

Two scores, both on 0-100:

  * **engagement_score** — higher is better. A weighted blend of
    today's activity-snapshot fields against per-metric targets.
  * **churn_risk_score** — higher means MORE likely to churn. Driven by
    inactivity gaps, broken streaks, and low recent engagement.

The numbers are intentionally simple to keep the model interpretable
(an admin can read the explanation). Tune the weights / targets per
cohort via ``settings.MOTIVATION_ENGAGEMENT_TARGETS`` later if needed.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.contrib.auth import get_user_model
from django.db.models import Sum
from django.utils import timezone

from ..models import LearnerActivitySnapshot


User = get_user_model()


# Targets — value at which the metric contributes its full weight.
TARGETS = {
    "lessons_completed":  1,      # 1 lesson/day
    "ai_chat_minutes":   10,     # 10 minutes of tutor per day
    "current_streak_days": 7,    # one solid week
    "reading_minutes":   10,
    "quiz_accuracy":    80.0,
}

# Weights — must sum to 1.0.
WEIGHTS = {
    "lessons_completed":   0.30,
    "ai_chat_minutes":     0.25,
    "current_streak_days": 0.20,
    "reading_minutes":     0.15,
    "quiz_accuracy":       0.10,
}


def _capped_ratio(value: float, target: float) -> float:
    if target <= 0:
        return 0.0
    return min(1.0, max(0.0, float(value) / float(target)))


def compute_engagement_score(snapshot: LearnerActivitySnapshot) -> float:
    """Blend the snapshot's metrics against TARGETS, returning 0-100."""
    parts = (
        WEIGHTS["lessons_completed"]   * _capped_ratio(snapshot.lessons_completed,   TARGETS["lessons_completed"]),
        WEIGHTS["ai_chat_minutes"]     * _capped_ratio(snapshot.ai_chat_minutes,     TARGETS["ai_chat_minutes"]),
        WEIGHTS["current_streak_days"] * _capped_ratio(snapshot.current_streak_days, TARGETS["current_streak_days"]),
        WEIGHTS["reading_minutes"]     * _capped_ratio(snapshot.reading_minutes,     TARGETS["reading_minutes"]),
        WEIGHTS["quiz_accuracy"]       * _capped_ratio(snapshot.quiz_accuracy,       TARGETS["quiz_accuracy"]),
    )
    return round(sum(parts) * 100.0, 1)


def compute_churn_risk_score(snapshot: LearnerActivitySnapshot, engagement_score: float | None = None) -> float:
    """Higher when the learner is more likely to disengage.

    Drivers, in priority order:
      * ``inactive_days``: >=14 → +60, >=7 → +35, >=3 → +15
      * No active streak: +10
      * Engagement score < 30: +25; < 50: +10
      * Recent 7-day average activity zero: +15
    """
    score = 0.0
    if snapshot.inactive_days >= 14:
        score += 60
    elif snapshot.inactive_days >= 7:
        score += 35
    elif snapshot.inactive_days >= 3:
        score += 15
    if snapshot.current_streak_days == 0:
        score += 10
    eng = engagement_score if engagement_score is not None else compute_engagement_score(snapshot)
    if eng < 30:
        score += 25
    elif eng < 50:
        score += 10
    # Cheap "is the last 7 days a desert?" check.
    week_ago = snapshot.date - timedelta(days=7)
    recent_lessons = (
        LearnerActivitySnapshot.objects
        .filter(user_id=snapshot.user_id, date__gt=week_ago, date__lte=snapshot.date)
        .aggregate(total=Sum("lessons_completed"))["total"] or 0
    )
    if recent_lessons == 0:
        score += 15
    return min(100.0, round(score, 1))


def compute_and_persist_for(snapshot: LearnerActivitySnapshot) -> LearnerActivitySnapshot:
    """Update both scores on a snapshot row and return it."""
    eng = compute_engagement_score(snapshot)
    risk = compute_churn_risk_score(snapshot, engagement_score=eng)
    snapshot.engagement_score = eng
    snapshot.churn_risk_score = risk
    snapshot.save(update_fields=["engagement_score", "churn_risk_score", "updated_at"])
    return snapshot


def compute_for_user(user) -> LearnerActivitySnapshot | None:
    """Refresh today's snapshot scores for one user. Returns the row or None."""
    today = timezone.localdate()
    snapshot = LearnerActivitySnapshot.objects.filter(user=user, date=today).first()
    if snapshot is None:
        return None
    return compute_and_persist_for(snapshot)


def at_risk_users(threshold: float = 60.0):
    """Latest-snapshot users whose churn_risk_score >= ``threshold``.

    Returns a queryset of ``LearnerActivitySnapshot`` (most recent per user).
    """
    today = timezone.localdate()
    return (
        LearnerActivitySnapshot.objects
        .filter(date=today, churn_risk_score__gte=threshold)
        .select_related("user")
        .order_by("-churn_risk_score")
    )


def run_nightly() -> int:
    """Cron-friendly: recompute scores for every user with a snapshot today.

    Returns the number of snapshots updated.
    """
    today = timezone.localdate()
    count = 0
    for snap in LearnerActivitySnapshot.objects.filter(date=today).iterator():
        compute_and_persist_for(snap)
        count += 1
    return count
