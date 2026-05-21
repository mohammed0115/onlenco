from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from courses.models import CourseEnrollment, CourseLessonProgress, Lesson
from teacher_portal.models import StudentAssignmentSubmission, TeacherAssignment
from teacher_portal.permissions import teacher_course_queryset


WEAKNESS_QUIZ_THRESHOLD = 60.0
# A student counts as "inactive" once they have not logged in for this
# many days (or have never logged in at all).
INACTIVE_AFTER_DAYS = 14


def _common_weaknesses(courses, limit: int = 5):
    """Skills where students most often score below the pass threshold.

    Returns ``[{"skill": <code>, "count": <n>}, …]`` ordered by count.
    """
    rows = (
        CourseLessonProgress.objects
        .filter(
            lesson__course__in=courses,
            quiz_score__isnull=False,
            quiz_score__lt=WEAKNESS_QUIZ_THRESHOLD,
        )
        .exclude(lesson__skill="")
        .values("lesson__skill")
        .annotate(count=Count("id"))
        .order_by("-count")[:limit]
    )
    return [
        {"skill": r["lesson__skill"], "count": r["count"]}
        for r in rows if r["lesson__skill"]
    ]


def _inactive_student_count(courses) -> int:
    """Distinct enrolled students who never logged in, or have not logged
    in within the last ``INACTIVE_AFTER_DAYS`` days.

    ``.order_by()`` clears CourseEnrollment's default ``-enrolled_at``
    ordering: without it, ``.values("user").distinct()`` leaks
    ``enrolled_at`` into the SELECT and the distinct count is inflated
    (one row per enrolment instead of one per student).
    """
    cutoff = timezone.now() - timedelta(days=INACTIVE_AFTER_DAYS)
    return (
        CourseEnrollment.objects
        .filter(course__in=courses)
        .filter(Q(user__last_login__isnull=True) | Q(user__last_login__lt=cutoff))
        .order_by()
        .values("user")
        .distinct()
        .count()
    )


def analytics_context(user):
    courses = teacher_course_queryset(user)
    progress = CourseLessonProgress.objects.filter(lesson__course__in=courses)
    assignments = TeacherAssignment.objects.filter(teacher=user)
    return {
        "course_rows": (
            courses
            .annotate(enrolled_count=Count("enrollments", distinct=True))
            .order_by("title")
        ),
        "completion_rate": round(
            progress.filter(completed_at__isnull=False).count()
            * 100 / max(progress.count(), 1),
            1,
        ),
        "quiz_average": round(
            progress.exclude(quiz_score__isnull=True)
            .aggregate(avg=Avg("quiz_score"))["avg"] or 0,
            1,
        ),
        # Lowest average quiz score first. Lessons with no quiz data at
        # all are excluded — a lesson nobody attempted is not "difficult".
        "difficult_lessons": (
            Lesson.objects.filter(course__in=courses)
            .annotate(avg_score=Avg("student_progress__quiz_score"))
            .filter(avg_score__isnull=False)
            .order_by("avg_score", "title")[:10]
        ),
        "inactive_students": _inactive_student_count(courses),
        "assignment_submissions": StudentAssignmentSubmission.objects.filter(
            assignment__in=assignments,
        ).count(),
        "common_weaknesses": _common_weaknesses(courses),
    }
