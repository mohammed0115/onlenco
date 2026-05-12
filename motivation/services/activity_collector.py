"""Roll up per-user learning activity into a daily LearnerActivitySnapshot.

This is the input to every other motivation service. It reads from existing
domain models (lessons, tutor, library, learning_core, weekly assessments)
and writes a single denormalised row per (user, date) so downstream services
can reason about a learner's day in O(1).
"""
from __future__ import annotations

import logging
from datetime import date as _date, datetime, time, timedelta
from typing import Iterable, List, Optional

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from ..models import LearnerActivitySnapshot

logger = logging.getLogger(__name__)
User = get_user_model()


def _day_window(target_date: _date):
    """Return aware (start, end) datetimes covering `target_date`."""
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(target_date, time.min), tz)
    end = start + timedelta(days=1)
    return start, end


def _safe_count(qs) -> int:
    try:
        return qs.count()
    except Exception:
        return 0


def _safe_sum(qs, field: str) -> int:
    try:
        from django.db.models import Sum
        result = qs.aggregate(s=Sum(field))["s"]
        return int(result or 0)
    except Exception:
        return 0


def _collect_lesson_metrics(user, start, end) -> dict:
    """Count completed lessons across three independent activity sources
    on the day: the legacy `lessons.Lesson`, the new courses-app
    `courses.Lesson`, and `daily_learning.DailyLearningPlan`. They are
    distinct content streams — a student who completes one of each on
    the same day counts three times.

    Without the third source, a daily-learning learner who never opens
    a regular lesson would never see their streak tick — that bug
    surfaced in the A0 student-journey simulation."""
    total = 0
    try:
        from lessons.models import LessonProgress
        total += _safe_count(LessonProgress.objects.filter(
            user=user,
            completed_at__gte=start,
            completed_at__lt=end,
        ))
    except Exception:
        pass
    try:
        from courses.models import CourseLessonProgress
        total += _safe_count(CourseLessonProgress.objects.filter(
            user=user,
            completed_at__gte=start,
            completed_at__lt=end,
        ))
    except Exception:
        pass
    try:
        from daily_learning.models import DailyLearningPlan
        total += _safe_count(DailyLearningPlan.objects.filter(
            user=user,
            status="completed",
            completed_at__gte=start,
            completed_at__lt=end,
        ))
    except Exception:
        pass
    return {"lessons_completed": total}


def _collect_tutor_metrics(user, start, end) -> dict:
    """Approximate AI-tutor minutes from message timestamps within the day.

    We use messages_count × 0.5 minute as a conservative proxy when no
    explicit timing is recorded by the tutor app.
    """
    try:
        from tutor.models import TutorMessage
    except Exception:
        return {"ai_chat_minutes": 0, "ai_messages_count": 0}
    qs = TutorMessage.objects.filter(
        conversation__user=user,
        created_at__gte=start,
        created_at__lt=end,
    )
    n = _safe_count(qs)
    return {
        "ai_messages_count": n,
        "ai_chat_minutes": int(round(n * 0.5)),
    }


def _collect_library_metrics(user, start, end) -> dict:
    try:
        from library.models import LibraryProgress, Chapter
    except Exception:
        return {"reading_minutes": 0, "words_read": 0}
    qs = LibraryProgress.objects.filter(
        user=user,
        updated_at__gte=start,
        updated_at__lt=end,
    ).select_related("chapter")
    words = 0
    minutes = 0
    for prog in qs:
        chapter = getattr(prog, "chapter", None)
        if chapter is None:
            continue
        # Estimate by `last_position` or chapter content length if available
        text = getattr(chapter, "content", "") or getattr(chapter, "text", "") or ""
        wc = len(text.split()) if text else 0
        if prog.completed:
            words += wc
        else:
            words += min(wc, max(0, prog.last_position or 0))
        minutes += 5 if prog.completed else 2
    return {"reading_minutes": minutes, "words_read": words}


def _collect_quiz_metrics(user, start, end) -> dict:
    """Combine lessons.Quiz attempts + adaptive ExerciseAttempt + WeeklyAssessment."""
    questions = 0
    correct = 0
    quizzes_completed = 0
    weekly_done = 0

    try:
        from learning_core.models import ExerciseAttempt
        qs = ExerciseAttempt.objects.filter(
            user=user, created_at__gte=start, created_at__lt=end
        )
        questions += _safe_count(qs)
        correct += _safe_count(qs.filter(is_correct=True))
    except Exception:
        pass

    try:
        from learning_core.models import WeeklyAssessment
        qs = WeeklyAssessment.objects.filter(
            user=user,
            status="completed",
            completed_at__gte=start,
            completed_at__lt=end,
        )
        weekly_done = _safe_count(qs)
    except Exception:
        pass

    try:
        from lessons.models import LessonProgress
        qs = LessonProgress.objects.filter(
            user=user,
            quiz_passed=True,
            last_attempt_at__gte=start,
            last_attempt_at__lt=end,
        )
        quizzes_completed = _safe_count(qs)
    except Exception:
        pass

    accuracy = (correct / questions * 100.0) if questions else 0.0
    return {
        "questions_answered": questions,
        "correct_answers": correct,
        "quiz_accuracy": round(accuracy, 2),
        "quizzes_completed": quizzes_completed,
        "weekly_assessments_completed": weekly_done,
    }


def _collect_profile_metrics(user) -> dict:
    """Pull CEFR + theta from learning_profile if present."""
    try:
        prof = getattr(user, "learning_profile", None)
        if prof is None:
            from learning_core.models import StudentLearningProfile
            prof = StudentLearningProfile.objects.filter(user=user).first()
        if prof is None:
            return {"cefr_level": "", "theta_score": 0.0}
        return {
            "cefr_level": getattr(prof, "current_cefr_level", "") or "",
            "theta_score": float(getattr(prof, "theta_score", 0.0) or 0.0),
        }
    except Exception:
        return {"cefr_level": "", "theta_score": 0.0}


def _previous_snapshot(user, target_date: _date) -> Optional[LearnerActivitySnapshot]:
    return (
        LearnerActivitySnapshot.objects
        .filter(user=user, date__lt=target_date)
        .order_by("-date")
        .first()
    )


def _streak_state(user, target_date: _date, has_activity_today: bool) -> dict:
    """Compute streak + inactive_days based on last snapshot + today's activity."""
    prev = _previous_snapshot(user, target_date)
    inactive_days = 0
    streak_days = 0

    if prev is None:
        if has_activity_today:
            streak_days = 1
        return {"current_streak_days": streak_days, "inactive_days": inactive_days}

    gap = (target_date - prev.date).days
    if has_activity_today:
        if gap == 1:
            streak_days = (prev.current_streak_days or 0) + 1
        elif gap == 0:
            streak_days = max(prev.current_streak_days or 0, 1)
        else:
            streak_days = 1
        inactive_days = 0
    else:
        streak_days = 0 if gap > 1 else (prev.current_streak_days or 0)
        inactive_days = gap

    return {"current_streak_days": streak_days, "inactive_days": inactive_days}


def collect_daily_activity(user, date: Optional[_date] = None) -> LearnerActivitySnapshot:
    """Build (or update) a LearnerActivitySnapshot for one user on one day."""
    if date is None:
        date = timezone.localdate()
    start, end = _day_window(date)

    metrics = {}
    metrics.update(_collect_lesson_metrics(user, start, end))
    metrics.update(_collect_tutor_metrics(user, start, end))
    metrics.update(_collect_library_metrics(user, start, end))
    metrics.update(_collect_quiz_metrics(user, start, end))
    profile = _collect_profile_metrics(user)

    has_activity = any(
        bool(metrics.get(k))
        for k in (
            "lessons_completed",
            "ai_messages_count",
            "questions_answered",
            "words_read",
            "weekly_assessments_completed",
        )
    )
    streak = _streak_state(user, date, has_activity)

    # Mastery delta = today's theta - previous snapshot's theta
    prev = _previous_snapshot(user, date)
    prev_theta = float(prev.theta_score) if prev else 0.0
    mastery_delta = round(profile["theta_score"] - prev_theta, 4)

    defaults = {
        "lessons_completed": metrics.get("lessons_completed", 0),
        "quizzes_completed": metrics.get("quizzes_completed", 0),
        "questions_answered": metrics.get("questions_answered", 0),
        "correct_answers": metrics.get("correct_answers", 0),
        "quiz_accuracy": metrics.get("quiz_accuracy", 0.0),
        "ai_chat_minutes": metrics.get("ai_chat_minutes", 0),
        "ai_messages_count": metrics.get("ai_messages_count", 0),
        "reading_minutes": metrics.get("reading_minutes", 0),
        "words_read": metrics.get("words_read", 0),
        "weekly_assessments_completed": metrics.get("weekly_assessments_completed", 0),
        "current_streak_days": streak["current_streak_days"],
        "inactive_days": streak["inactive_days"],
        "cefr_level": profile["cefr_level"],
        "theta_score": profile["theta_score"],
        "mastery_delta": mastery_delta,
    }

    with transaction.atomic():
        snap, created = LearnerActivitySnapshot.objects.update_or_create(
            user=user, date=date, defaults=defaults
        )
    return snap


def collect_all_active_users(date: Optional[_date] = None) -> List[LearnerActivitySnapshot]:
    """Run collection for every user who has a Profile."""
    if date is None:
        date = timezone.localdate()
    snapshots: List[LearnerActivitySnapshot] = []
    for user in User.objects.filter(is_active=True).iterator():
        try:
            snapshots.append(collect_daily_activity(user, date))
        except Exception as e:
            logger.exception("collect_daily_activity failed for user %s: %s", user.pk, e)
    return snapshots
