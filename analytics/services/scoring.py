"""Behavioral analytics scoring services.

Public API:
    engagement_score(user, days=30) -> int (0..100)
    churn_risk(user) -> str ("low" | "medium" | "high")
    learning_speed_for(user, days=14) -> float
    improvement_trend(user, days=30) -> list[dict]   # daily series
    persist_for_user(user) -> dict                   # writes to profile.metadata

The signals are computed from data we already collect:
    - LearnerActivitySnapshot (per-day rollup)
    - ExerciseAttempt        (time_spent_seconds + is_correct)
    - StudentLearningProfile (theta_score, current_cefr_level, learning_speed)
    - SkillMastery           (mastery_score)
"""
from __future__ import annotations

import statistics
from datetime import date as _date, timedelta
from typing import Optional

from django.utils import timezone


# ---------------------------------------------------------------------------
# Engagement score
# ---------------------------------------------------------------------------

def engagement_score(user, days: int = 30) -> int:
    """0..100 weighted blend of activity, accuracy, streak, AI-tutor minutes.

    Weights:
        40 % active-days ratio   (snapshots-with-activity / days)
        30 % avg quiz accuracy
        20 % current streak (saturates at 14 days)
        10 % AI-tutor minutes (saturates at 60 min/week-equivalent)
    """
    try:
        from motivation.models import LearnerActivitySnapshot
    except Exception:
        return 0

    today = timezone.localdate()
    horizon = today - timedelta(days=max(1, days))
    snaps = list(
        LearnerActivitySnapshot.objects
        .filter(user=user, date__gte=horizon, date__lte=today)
        .order_by("date")
    )
    if not snaps:
        return 0

    active = [s for s in snaps if (
        (s.lessons_completed or 0)
        or (s.questions_answered or 0)
        or (s.ai_messages_count or 0)
        or (s.words_read or 0)
    )]
    active_ratio = len(active) / max(1, days)

    accs = [s.quiz_accuracy or 0 for s in snaps if (s.questions_answered or 0) > 0]
    accuracy = (sum(accs) / len(accs)) if accs else 0.0  # 0..100

    streak = max((s.current_streak_days or 0) for s in snaps[-3:])
    streak_signal = min(streak / 14.0, 1.0)  # saturate at 2 weeks

    ai_minutes = sum((s.ai_chat_minutes or 0) for s in snaps[-7:])
    ai_signal = min(ai_minutes / 60.0, 1.0)  # 60 min/week saturates

    score = (
        0.40 * (active_ratio * 100.0)
        + 0.30 * accuracy
        + 0.20 * (streak_signal * 100.0)
        + 0.10 * (ai_signal * 100.0)
    )
    return max(0, min(100, int(round(score))))


# ---------------------------------------------------------------------------
# Churn risk
# ---------------------------------------------------------------------------

def churn_risk(user) -> str:
    """Rule-based churn classifier.

        - high   : last activity 8+ days ago
                   OR (≥3 days inactive AND mastery < 40)
        - medium : 4–7 days inactive
                   OR engagement_score < 35
        - low    : otherwise
    """
    try:
        from motivation.models import LearnerActivitySnapshot
        from learning_core.models import SkillMastery
        from django.db.models import Avg
    except Exception:
        return "low"

    last = (
        LearnerActivitySnapshot.objects
        .filter(user=user)
        .order_by("-date")
        .first()
    )
    inactive = 0
    if last:
        inactive = max((timezone.localdate() - last.date).days, last.inactive_days or 0)
    else:
        # No snapshot history at all — default to medium until they engage.
        return "medium"

    avg_mastery = (
        SkillMastery.objects.filter(user=user)
        .aggregate(avg=Avg("mastery_score"))
        .get("avg")
    ) or 0.0

    if inactive >= 8:
        return "high"
    if inactive >= 3 and avg_mastery < 40:
        return "high"
    if 4 <= inactive <= 7:
        return "medium"
    if engagement_score(user, days=30) < 35:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Learning speed
# ---------------------------------------------------------------------------

def learning_speed_for(user, days: int = 14) -> float:
    """Rebased learning speed: 1.0 baseline, lower means faster.

    Uses the median time-on-correct-answer over the window. The baseline
    is 30 seconds — ~ what the AI exercise generator targets. A user who
    answers correctly in 15s gets speed=2.0; in 60s gets speed=0.5.
    """
    try:
        from learning_core.models import ExerciseAttempt
    except Exception:
        return 1.0

    horizon = timezone.now() - timedelta(days=max(1, days))
    times = list(
        ExerciseAttempt.objects
        .filter(user=user, is_correct=True, created_at__gte=horizon, time_spent_seconds__gt=0)
        .values_list("time_spent_seconds", flat=True)[:200]
    )
    if not times:
        return 1.0
    median = statistics.median(times)
    if median <= 0:
        return 1.0
    baseline = 30.0
    speed = baseline / median
    # Clamp to [0.25, 4.0] so a single quick answer doesn't wreck the metric.
    return round(max(0.25, min(4.0, speed)), 2)


# ---------------------------------------------------------------------------
# Per-user improvement trend (for charts)
# ---------------------------------------------------------------------------

def improvement_trend(user, days: int = 30) -> list[dict]:
    """List of `{date, theta, mastery, accuracy}` for the last `days` days.

    Snapshots are dense (one row per active day); we backfill missing days
    with the previous value so a chart can render a continuous line.
    """
    try:
        from motivation.models import LearnerActivitySnapshot
    except Exception:
        return []

    today = timezone.localdate()
    horizon = today - timedelta(days=max(1, days) - 1)
    rows = list(
        LearnerActivitySnapshot.objects
        .filter(user=user, date__gte=horizon)
        .order_by("date")
        .values("date", "theta_score", "quiz_accuracy", "current_streak_days")
    )
    if not rows:
        return []

    by_date = {r["date"]: r for r in rows}
    out: list[dict] = []
    last_theta = 0.0
    last_accuracy = 0.0
    cur = horizon
    while cur <= today:
        r = by_date.get(cur)
        if r:
            last_theta = float(r["theta_score"] or last_theta)
            last_accuracy = float(r["quiz_accuracy"] or last_accuracy)
        out.append({
            "date": cur.isoformat(),
            "theta": round(last_theta, 4),
            "accuracy": round(last_accuracy, 1),
            "streak": (r["current_streak_days"] if r else 0) or 0,
        })
        cur += timedelta(days=1)
    return out


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def persist_for_user(user) -> dict:
    """Compute all three scalars + persist onto the learning profile.

    Stores under `profile.metadata['behavior']` so it's a single read for
    the dashboard / API. Also updates `profile.learning_speed` (the model
    field that previously was never written from data).
    """
    try:
        from learning_core.models import StudentLearningProfile
    except Exception:
        return {}

    data = {
        "engagement_score": engagement_score(user),
        "churn_risk": churn_risk(user),
        "learning_speed": learning_speed_for(user),
        "computed_at": timezone.now().isoformat(),
    }
    profile = StudentLearningProfile.objects.filter(user=user).first()
    if profile:
        meta = profile.metadata or {}
        meta["behavior"] = data
        profile.metadata = meta
        # Mirror onto the dedicated field so existing serialisers see it.
        profile.learning_speed = data["learning_speed"]
        profile.save(update_fields=["metadata", "learning_speed", "updated_at"])
    return data


def persist_for_all() -> dict:
    """Cron entry-point — runs `persist_for_user` for every user with a
    learning profile."""
    try:
        from learning_core.models import StudentLearningProfile
    except Exception:
        return {"users": 0}

    users_done = 0
    errors = 0
    for prof in StudentLearningProfile.objects.select_related("user").iterator():
        try:
            persist_for_user(prof.user)
            users_done += 1
        except Exception:
            errors += 1
    return {"users": users_done, "errors": errors}
