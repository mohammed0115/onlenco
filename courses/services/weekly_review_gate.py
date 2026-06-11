"""Weekly Review gate (Prompt 18.3C).

A CourseUnit holds 3 lessons, so a "weekly review" is logically due once a
learner has completed all lessons in a unit. This module is a READ-ONLY
decision helper: it inspects ``CourseLessonProgress`` and returns a flag for the
dashboard/UI. It NEVER writes progress, never unlocks/locks lessons, and never
blocks the learner — it only *recommends* a review.

No new model is introduced; the existing ``CourseReview`` /
``WeeklyAssessment`` can be layered on later. This is the minimal safe gate.
"""
from __future__ import annotations

from .. import models as m


def _unit_lesson_ids(course_unit) -> list[int]:
    return list(
        m.Lesson.objects.filter(unit=course_unit, is_active=True)
        .values_list("id", flat=True)
    )


def should_show_weekly_review(user, course_unit) -> bool:
    """True once EVERY active lesson in ``course_unit`` is completed by ``user``.

    Pure read of ``CourseLessonProgress.completed_at``. No writes, no side
    effects, never blocks access.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    lesson_ids = _unit_lesson_ids(course_unit)
    if not lesson_ids:
        return False
    done = (
        m.CourseLessonProgress.objects
        .filter(user=user, lesson_id__in=lesson_ids, completed_at__isnull=False)
        .values_list("lesson_id", flat=True)
        .distinct()
        .count()
    )
    return done >= len(lesson_ids)


def pending_weekly_reviews(user, course) -> list:
    """Units in ``course`` whose weekly review is due (all 3 lessons done).

    Read-only; returns a list of CourseUnit rows for the dashboard to surface.
    """
    units = m.CourseUnit.objects.filter(course=course, is_active=True).order_by("order")
    return [u for u in units if should_show_weekly_review(user, u)]
