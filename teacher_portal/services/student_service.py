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


# CEFR order for grouping; "—" collects students with no level yet.
_LEVEL_ORDER = ["A0", "A1", "A2", "B1", "B2", "C1", "C2", "C3", "—"]
_LEVEL_LABELS = {
    "A0": ("Absolute beginner", "مبتدئ تمامًا"),
    "A1": ("Beginner", "مبتدئ"),
    "A2": ("Elementary", "أساسي"),
    "B1": ("Intermediate", "متوسط"),
    "B2": ("Upper-intermediate", "فوق المتوسط"),
    "C1": ("Advanced", "متقدم"),
    "C2": ("Proficient", "متمكّن"),
    "C3": ("Mastery", "إتقان"),
    "—": ("Not placed yet", "بدون مستوى"),
}


def teacher_student_groups(user):
    """Group the teacher's unique students by CEFR level for the Groups page.

    Each group lists its students with aggregated progress + quiz average
    across this teacher's courses. Read-only; respects course ownership.
    """
    courses = teacher_course_queryset(user)
    enrollments = (
        CourseEnrollment.objects.filter(course__in=courses)
        .select_related("user", "user__profile")
    )
    quiz_avgs = dict(
        CourseLessonProgress.objects
        .filter(lesson__course__in=courses, quiz_score__isnull=False)
        .values("user")
        .annotate(avg=Avg("quiz_score"))
        .values_list("user", "avg")
    )
    by_student: dict = {}
    for e in enrollments:
        s = e.user
        entry = by_student.setdefault(s.pk, {
            "student": s,
            "level": (getattr(getattr(s, "profile", None), "cefr_level", "") or "—"),
            "courses": 0,
            "_progress_sum": 0.0,
            "quiz_average": quiz_avgs.get(s.pk),
        })
        entry["courses"] += 1
        entry["_progress_sum"] += e.progress_percentage or 0
    for entry in by_student.values():
        entry["avg_progress"] = round(entry["_progress_sum"] / max(entry["courses"], 1), 1)
        entry.pop("_progress_sum", None)

    grouped: dict = {}
    for entry in by_student.values():
        grouped.setdefault(entry["level"], []).append(entry)
    groups = []
    for level in _LEVEL_ORDER:
        students = sorted(grouped.get(level, []), key=lambda x: x["student"].get_username())
        if not students:
            continue
        en, ar = _LEVEL_LABELS.get(level, (level, level))
        groups.append({"level": level, "label_en": en, "label_ar": ar, "students": students, "count": len(students)})
    return groups


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

