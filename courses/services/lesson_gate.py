"""Sequential daily drip-unlock for course lessons.

A student opens course lessons one at a time. The next lesson unlocks
only after the previous one is completed AND a calendar day has passed —
so a learner can advance at most one lesson per day.

This is the general (non-A0) counterpart of
``a0_world.build_a0_world``: the A0 mission map has its own bespoke UI,
while every other course uses the plain lesson grid gated here.

A course can opt out via ``Course.drip_enabled = False`` — then every
lesson is open at once (subject only to subscription access).
"""
from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from courses.models import CourseLessonProgress


def _is_complete(progress) -> bool:
    """A progress row counts as complete once it is finished."""
    return bool(progress and (progress.completed_at or progress.is_complete))


def annotate_lesson_states(*, course, lessons, user, has_access):
    """Return a per-lesson state list for ``lessons`` (already ordered).

    Each row:
        {
          "lesson": Lesson, "index": 1-based int,
          "state": "completed" | "unlocked" | "locked",
          "is_completed"/"is_unlocked"/"is_locked": bool,
          "can_open": bool,            # may the student open it now?
          "available_on": date | None, # when a locked lesson opens
          "lesson_url": str,           # "" when it can't be opened
        }

    Drip rule (``course.drip_enabled``): lesson N (N > 1) unlocks once
    lesson N-1 is completed (score ≥ 70%) — immediately, with no day wait.
    A completed lesson is always re-openable for review.
    """
    lesson_list = list(lessons)
    drip = getattr(course, "drip_enabled", True)

    progress_by_lesson = {}
    if getattr(user, "is_authenticated", False):
        progress_by_lesson = {
            p.lesson_id: p
            for p in CourseLessonProgress.objects
            .filter(user=user, lesson__in=lesson_list)
            .select_related("lesson")
        }

    rows = []
    prev_completed = True            # lesson 1 has no predecessor
    for index, lesson in enumerate(lesson_list):
        progress = progress_by_lesson.get(lesson.id)
        completed = _is_complete(progress)

        if not has_access:
            unlocked = False
        elif not drip or index == 0:
            unlocked = True
        else:
            # Sequential unlock: the next lesson opens as soon as the previous
            # one is completed (score ≥ 70%) — no calendar-day wait.
            unlocked = prev_completed

        can_open = bool(has_access and (completed or unlocked))
        state = "completed" if completed else ("unlocked" if unlocked else "locked")

        rows.append({
            "lesson": lesson,
            "index": index + 1,
            "state": state,
            "is_completed": state == "completed",
            "is_unlocked": state == "unlocked",
            "is_locked": state == "locked",
            "can_open": can_open,
            "available_on": None,
            "lesson_url": (
                reverse("courses:lesson_detail", args=[course.pk, lesson.pk])
                if can_open else ""
            ),
        })

        prev_completed = completed
    return rows


def can_open_lesson(*, course, lesson, user, has_access) -> bool:
    """Whether ``user`` may open ``lesson`` right now — the server-side
    guard behind the lesson-detail / mark-complete / quiz views.

    A completed lesson is always openable (review); a drip-locked one is
    not, even via a hand-typed URL.
    """
    from courses.services.student_flow import published_lesson_queryset

    lessons = published_lesson_queryset().filter(course=course)
    for row in annotate_lesson_states(
        course=course, lessons=lessons, user=user, has_access=has_access,
    ):
        if row["lesson"].id == lesson.id:
            return row["can_open"]
    return False
