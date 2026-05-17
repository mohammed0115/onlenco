from __future__ import annotations

from django.db.models import Avg, Count, Q
from django.utils import timezone

from courses.models import CourseLessonProgress, Lesson
from teacher_portal.models import StudentAssignmentSubmission, TeacherAssignment
from teacher_portal.permissions import teacher_course_queryset


def dashboard_context(user):
    courses = teacher_course_queryset(user)
    today = timezone.localdate()
    students = courses.values("enrollments__user").exclude(enrollments__user__isnull=True).distinct()
    progress = CourseLessonProgress.objects.filter(lesson__course__in=courses)
    active_students = courses.filter(enrollments__user__last_login__date=today).values("enrollments__user").distinct().count()
    delayed_students = courses.filter(enrollments__progress_percentage__lt=25).values("enrollments__user").distinct().count()
    lessons_without_quizzes = Lesson.objects.filter(course__in=courses).annotate(q_count=Count("quiz")).filter(q_count=0)
    assignments = TeacherAssignment.objects.filter(teacher=user)
    return {
        "metrics": {
            "courses": courses.count(),
            "published": courses.filter(status="published").count(),
            "draft": courses.filter(status="draft").count(),
            "pending_review": courses.filter(status="pending_review").count(),
            "rejected": courses.filter(status="rejected").count(),
            "students": students.count(),
            "active_students": active_students,
            "delayed_students": delayed_students,
            "completion_rate": round(progress.filter(completed_at__isnull=False).count() * 100 / max(progress.count(), 1), 1),
            "quiz_average": round(progress.exclude(quiz_score__isnull=True).aggregate(avg=Avg("quiz_score"))["avg"] or 0, 1),
            "assignments_submitted": StudentAssignmentSubmission.objects.filter(assignment__in=assignments).count(),
        },
        "pending_tasks": {
            "courses_need_completion": courses.filter(status__in=["draft", "rejected"]).count(),
            "lessons_need_review": Lesson.objects.filter(course__in=courses, status__in=["draft", "rejected"]).count(),
            "quizzes_need_questions": lessons_without_quizzes.count(),
        },
        "recent_courses": courses.select_related("level").order_by("-updated_at")[:6],
        "recent_submissions": StudentAssignmentSubmission.objects.filter(assignment__in=assignments).select_related("student", "assignment")[:6],
    }

