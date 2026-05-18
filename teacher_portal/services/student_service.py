from __future__ import annotations

from django.db.models import Avg, Max, Q

from courses.models import CourseEnrollment, CourseLessonProgress, Lesson
from platform_admin.services.audit_log_service import log_action

from teacher_portal.models import TeacherStudentNote
from teacher_portal.permissions import teacher_course_queryset


WEAKNESS_QUIZ_THRESHOLD = 60.0


def _weakness_skills_for_student(student, courses):
    weak = (
        CourseLessonProgress.objects
        .filter(user=student, lesson__course__in=courses, quiz_score__isnull=False, quiz_score__lt=WEAKNESS_QUIZ_THRESHOLD)
        .values_list("lesson__skill", flat=True)
        .distinct()
    )
    return [s for s in weak if s]


def teacher_student_rows(user, *, search: str = ""):
    courses = teacher_course_queryset(user)
    enrollments = (
        CourseEnrollment.objects.filter(course__in=courses)
        .select_related("user", "user__profile", "course")
        .order_by("user__email", "course__title")
    )
    if search:
        enrollments = enrollments.filter(
            Q(user__email__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__profile__full_name__icontains=search)
        )
    rows = []
    for enrollment in enrollments:
        progress = CourseLessonProgress.objects.filter(
            user=enrollment.user,
            lesson__course=enrollment.course,
        )
        weaknesses = _weakness_skills_for_student(enrollment.user, [enrollment.course])
        rows.append({
            "student": enrollment.user,
            "course": enrollment.course,
            "progress": enrollment.progress_percentage,
            "last_activity": progress.aggregate(last=Max("updated_at"))["last"],
            "quiz_average": progress.exclude(quiz_score__isnull=True).aggregate(avg=Avg("quiz_score"))["avg"],
            "weaknesses": ", ".join(weaknesses) if weaknesses else "-",
            "status": enrollment.status,
        })
    return rows


def teacher_student_detail_context(teacher, student):
    courses = teacher_course_queryset(teacher)
    enrollments = CourseEnrollment.objects.filter(user=student, course__in=courses).select_related("course")
    progress = CourseLessonProgress.objects.filter(user=student, lesson__course__in=courses).select_related("lesson", "lesson__course")
    notes = TeacherStudentNote.objects.filter(teacher=teacher, student=student, course__in=courses).select_related("course")
    return {
        "student": student,
        "enrollments": enrollments,
        "progress": progress,
        "notes": notes,
    }


def add_student_note(request, form, student):
    note = form.save(commit=False)
    note.teacher = request.user
    note.student = student
    note.save()
    log_action(
        request,
        action_type="teacher.student.note",
        target_user=student,
        object_type="TeacherStudentNote",
        object_id=note.pk,
        description=f"Teacher added note for {student.email or student.username}",
        metadata={"course_id": note.course_id, "visibility": note.visibility},
    )
    return note

