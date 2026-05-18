from __future__ import annotations

from django.db.models import Avg, Count

from courses.models import CourseLessonProgress, Lesson
from teacher_portal.models import StudentAssignmentSubmission, TeacherAssignment
from teacher_portal.permissions import teacher_course_queryset


WEAKNESS_QUIZ_THRESHOLD = 60.0


def _common_weaknesses(courses, limit: int = 5):
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
    return [r["lesson__skill"] for r in rows if r["lesson__skill"]]


def analytics_context(user):
    courses = teacher_course_queryset(user)
    progress = CourseLessonProgress.objects.filter(lesson__course__in=courses)
    assignments = TeacherAssignment.objects.filter(teacher=user)
    return {
        "course_rows": courses.annotate(enrolled_count=Count("enrollments", distinct=True)).order_by("title"),
        "completion_rate": round(progress.filter(completed_at__isnull=False).count() * 100 / max(progress.count(), 1), 1),
        "quiz_average": round(progress.exclude(quiz_score__isnull=True).aggregate(avg=Avg("quiz_score"))["avg"] or 0, 1),
        "difficult_lessons": (
            Lesson.objects.filter(course__in=courses)
            .annotate(avg_score=Avg("student_progress__quiz_score"))
            .order_by("avg_score", "title")[:10]
        ),
        "inactive_students": courses.filter(enrollments__user__last_login__isnull=True).values("enrollments__user").distinct().count(),
        "assignment_submissions": StudentAssignmentSubmission.objects.filter(assignment__in=assignments).count(),
        "common_weaknesses": _common_weaknesses(courses),
    }
