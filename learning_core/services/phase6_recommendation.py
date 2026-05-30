"""Recommendation engine — Phase 6 (rule-based, no AI).

Returns a small dict the Summary template / dashboard can render.

Priority order:
  1. Due review mistakes
  2. Failed last Challenge → retry
  3. Weakest skill (mastery < 50)
  4. Daily goal not yet hit
  5. Default — continue to next lesson
"""
from __future__ import annotations

from typing import Optional

from . import smart_review_service


def get_next_best_action(user) -> dict:
    """Return one recommendation. Shape:
        { kind: str, title_en: str, title_ar: str, payload: dict }
    """
    # 1. Due reviews
    due_count = smart_review_service.count_due_now(user)
    if due_count:
        return {
            "kind": "review_mistakes",
            "title_en": f"Review {due_count} mistake{'s' if due_count != 1 else ''}",
            "title_ar": f"راجع {due_count} خطأ",
            "payload": {"due_count": due_count},
        }

    # 2. Failed last Challenge
    from courses.models import ChallengeSession
    last = (
        ChallengeSession.objects.filter(user=user)
        .order_by("-updated_at").first()
    )
    if last is not None and last.status == "failed":
        return {
            "kind": "retry_challenge",
            "title_en": "Retry the challenge",
            "title_ar": "أعد المحاولة في التحدي",
            "payload": {
                "lesson_id": last.lesson_id,
                "course_id": last.lesson.course_id if last.lesson_id else None,
            },
        }

    # 3. Weakest skill
    weak = get_weak_skills(user, limit=1)
    if weak:
        s = weak[0]["skill"]
        return {
            "kind": "practice_skill",
            "title_en": f"Practice {s.display_title}",
            "title_ar": f"تدرّب على {s.title_ar or s.display_title}",
            "payload": {"skill_code": s.code, "mastery_score": weak[0]["mastery_score"]},
        }

    # 4. Daily goal not completed
    try:
        from motivation.services import daily_goal_service
        goal = daily_goal_service.get_daily_goal_summary(user)
    except Exception:
        goal = None
    if goal and not goal.get("completed"):
        return {
            "kind": "daily_goal",
            "title_en": f"Complete today's goal ({goal['earned']}/{goal['target']} XP)",
            "title_ar": f"حقّق هدفك اليومي ({goal['earned']}/{goal['target']} XP)",
            "payload": goal,
        }

    # 5. Default — continue next lesson
    return {
        "kind": "continue_lesson",
        "title_en": "Continue to the next lesson",
        "title_ar": "تابع إلى الدرس التالي",
        "payload": {},
    }


def get_weak_skills(user, *, limit: int = 5) -> list[dict]:
    """Return `[{skill, mastery_score, confidence}, ...]` for the user's
    weakest practiced skills (mastery < 50)."""
    from ..models import SkillMastery
    rows = (
        SkillMastery.objects
        .filter(user=user, mastery_score__lt=50, attempts_count__gt=0)
        .select_related("skill")
        .order_by("mastery_score")[:limit]
    )
    return [
        {
            "skill":         r.skill,
            "mastery_score": r.mastery_score,
            "confidence":    r.confidence_level,
        }
        for r in rows
    ]


def get_recommended_review(user, *, limit: int = 10) -> list[dict]:
    return smart_review_service.build_review_queue(user, limit=limit)


def get_recommended_lesson(user):
    """Pick the next not-yet-completed published lesson the user has
    access to. Returns a Lesson or None."""
    from courses.models import CourseLessonProgress, Lesson
    progressed_ids = set(
        CourseLessonProgress.objects.filter(
            user=user, completed_at__isnull=False,
        ).values_list("lesson_id", flat=True)
    )
    return (
        Lesson.objects.filter(status="published", is_active=True)
        .exclude(pk__in=progressed_ids)
        .order_by("course_id", "order")
        .first()
    )


def get_mastery_summary(user) -> dict:
    """Bird's-eye view for the dashboard widget."""
    from ..models import SkillMastery
    rows = SkillMastery.objects.filter(user=user, attempts_count__gt=0)
    total = rows.count()
    avg = (
        sum(r.mastery_score for r in rows) / total
        if total else 0.0
    )
    by_band = {"new": 0, "learning": 0, "improving": 0, "strong": 0, "mastered": 0}
    for r in rows:
        by_band[r.confidence_level] = by_band.get(r.confidence_level, 0) + 1
    return {
        "skills_practiced": total,
        "avg_mastery":      round(avg, 1),
        "by_confidence":    by_band,
    }
