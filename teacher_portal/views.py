from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from courses.models import Course, CourseEnrollment, DigitalCertificate, Lesson, LessonQuestion, LessonQuiz
from notifications import constants as notification_constants
from notifications.models import NotificationEvent

from . import permissions as teacher_perms
from .forms import (
    LiveSessionForm,
    ReviewSubmissionForm,
    StudentAssignmentSubmissionForm,
    TeacherAssignmentForm,
    TeacherCourseForm,
    TeacherLessonForm,
    TeacherProfileForm,
    TeacherQuestionForm,
    TeacherQuizForm,
    TeacherStudentNoteForm,
)
from .models import LiveSession, StudentAssignmentSubmission, TeacherAssignment, TeacherProfile, TeacherStudentNote
from .permissions import teacher_required
from .services import (
    analytics_service,
    assignment_service,
    course_service,
    dashboard_service,
    lesson_service,
    live_session_service,
    meet_service,
    notification_service,
    quiz_service,
    student_service,
)
from .services.role_service import ROLE_STUDENT, ROLE_TEACHER, RoleService


def _teacher_nav():
    return [
        ("dashboard", "layout-dashboard", "Teacher Dashboard", "لوحة المعلم", "teacher_portal:dashboard"),
        ("courses", "book-open", "My Courses", "كورساتي", "teacher_portal:courses"),
        ("lessons", "play-square", "My Lessons", "دروسي", "teacher_portal:all_lessons"),
        ("quizzes", "list-checks", "Quizzes", "اختباراتي", "teacher_portal:all_quizzes"),
        ("students", "users", "My Students", "طلابي", "teacher_portal:students"),
        ("groups", "users-round", "Groups", "المجموعات", "teacher_portal:student_groups"),
        ("assignments", "clipboard-list", "Assignments", "الواجبات", "teacher_portal:assignments"),
        ("live_sessions", "video", "Live Sessions", "الحصص المباشرة", "teacher_portal:live_sessions"),
        ("analytics", "bar-chart-3", "Analytics", "التحليلات", "teacher_portal:analytics"),
        ("notifications", "bell", "Notifications", "الإشعارات", "teacher_portal:notifications"),
        ("settings", "settings", "Settings", "الإعدادات", "teacher_portal:settings"),
    ]


def _ctx(request, section: str, extra=None):
    context = {
        "section": section,
        "teacher_nav": _teacher_nav(),
        "active_role": RoleService.get_active_role(request),
        "available_modes": RoleService.available_modes(request.user),
        "can_access_control_center": RoleService.can_access_control_center(request.user),
        "show_student_mode": RoleService.user_has_role(request.user, ROLE_STUDENT),
        "available_staff_modes": RoleService.available_staff_modes(request.user),
    }
    if extra:
        context.update(extra)
    return context


def _render(request, template_name, section, context=None):
    return render(request, template_name, _ctx(request, section, context or {}))


def _paginate(request, qs, per_page=20):
    return Paginator(qs, per_page).get_page(request.GET.get("page") or 1)


@login_required
def switch_role(request, role):
    if role not in {ROLE_STUDENT, ROLE_TEACHER}:
        raise Http404("Unknown role")
    if not RoleService.set_active_role(request, role):
        return HttpResponseForbidden("Role is not available for this account")
    if role == ROLE_TEACHER:
        return redirect("teacher_portal:dashboard")
    return redirect("dashboard")


@login_required
def switch_staff_mode(request, mode):
    """Switch between Control Center and Teacher Portal for admin+teacher users."""
    if mode not in {"control", "teacher"}:
        raise Http404("Unknown staff mode")
    if mode == "control":
        if not RoleService.can_access_control_center(request.user):
            return HttpResponseForbidden("Control Center access required")
        request.session["active_staff_mode"] = "control"
        return redirect("platform_admin:dashboard")
    if not RoleService.is_teacher_user(request.user):
        return HttpResponseForbidden("Teacher role required")
    request.session["active_staff_mode"] = "teacher"
    return redirect("teacher_portal:dashboard")


@teacher_required
def dashboard(request):
    return _render(
        request,
        "teacher_portal/dashboard.html",
        "dashboard",
        dashboard_service.dashboard_context(request.user),
    )


_COURSE_SORT_KEYS = {
    # url-param → DB ordering (negative = DESC). Whitelist so no
    # arbitrary column name from query string ever reaches Django's
    # order_by — that'd be both an injection risk and a query-planner
    # surprise.
    "title":      "title",
    "-title":     "-title",
    "level":      "level__order",
    "-level":     "-level__order",
    "status":     "status",
    "-status":    "-status",
    "lessons":    "lessons_count",
    "-lessons":   "-lessons_count",
    "students":   "students_count",
    "-students":  "-students_count",
    "updated":    "updated_at",
    "-updated":   "-updated_at",
    "created":    "created_at",
    "-created":   "-created_at",
}
_COURSE_SORT_DEFAULT = "-updated"


@teacher_required
def courses_list(request):
    from django.db.models import Count
    qs = (
        teacher_perms.teacher_course_queryset(request.user)
        .select_related("level")
        .prefetch_related("lessons", "enrollments")
        .annotate(
            lessons_count=Count("lessons", distinct=True),
            students_count=Count("enrollments", distinct=True),
        )
    )
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    level = (request.GET.get("level") or "").strip()
    language = (request.GET.get("language") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(title_ar__icontains=q) | Q(title_en__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if level:
        qs = qs.filter(level__code=level)
    if language:
        qs = qs.filter(language=language)

    sort_param = (request.GET.get("sort") or _COURSE_SORT_DEFAULT).strip()
    ordering = _COURSE_SORT_KEYS.get(sort_param) or _COURSE_SORT_KEYS[_COURSE_SORT_DEFAULT]
    if sort_param not in _COURSE_SORT_KEYS:
        sort_param = _COURSE_SORT_DEFAULT
    qs = qs.order_by(ordering, "-id")

    return _render(
        request,
        "teacher_portal/courses/list.html",
        "courses",
        {
            "page_obj": _paginate(request, qs),
            "filters": request.GET,
            "sort_param": sort_param,
        },
    )


@teacher_required
def course_detail(request, pk):
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user).select_related("level", "teacher"), pk=pk)
    # Tag each lesson with whether this teacher may edit/delete it, so the
    # template only offers the actions the lesson views would actually
    # allow (draft/rejected own lessons) instead of buttons that 403.
    lessons = list(course.lessons.order_by("order", "id"))
    for lesson in lessons:
        lesson.can_edit = teacher_perms.teacher_can_edit_lesson(request.user, lesson)
    return _render(
        request,
        "teacher_portal/courses/detail.html",
        "courses",
        {
            "course": course,
            "lessons": lessons,
            "can_edit": teacher_perms.teacher_can_edit_course(request.user, course),
        },
    )


@teacher_required
def course_create(request):
    if request.method == "POST":
        form = TeacherCourseForm(request.POST, request.FILES)
        if form.is_valid():
            course = course_service.create_course(request, form)
            messages.success(request, "Course created as draft.")
            return redirect("teacher_portal:course_detail", pk=course.pk)
    else:
        form = TeacherCourseForm()
    return _render(request, "teacher_portal/courses/form.html", "courses", {"form": form, "course": None})


@teacher_required
def course_edit(request, pk):
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user), pk=pk)
    if not teacher_perms.teacher_can_edit_course(request.user, course):
        return HttpResponseForbidden("Only draft or rejected own courses can be edited")
    if request.method == "POST":
        form = TeacherCourseForm(request.POST, request.FILES, instance=course)
        if form.is_valid():
            course = course_service.update_course(request, form)
            messages.success(request, "Course updated.")
            return redirect("teacher_portal:course_detail", pk=course.pk)
    else:
        form = TeacherCourseForm(instance=course)
    return _render(request, "teacher_portal/courses/form.html", "courses", {"form": form, "course": course})


@require_POST
@teacher_required
def course_submit_review(request, pk):
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user), pk=pk)
    if course.status not in {"draft", "rejected"}:
        return HttpResponseForbidden("Course cannot be submitted in this status")
    course_service.submit_course_for_review(request, course)
    messages.success(request, "Course submitted for academic review.")
    return redirect("teacher_portal:course_detail", pk=course.pk)


_LESSON_SORT_KEYS = {
    "order":      "order",
    "-order":     "-order",
    "title":      "title",
    "-title":     "-title",
    "status":     "status",
    "-status":    "-status",
    "updated":    "updated_at",
    "-updated":   "-updated_at",
    "created":    "created_at",
    "-created":   "-created_at",
}
_LESSON_SORT_DEFAULT = "order"


@teacher_required
def lessons_list(request, course_id):
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user), pk=course_id)
    sort_param = (request.GET.get("sort") or _LESSON_SORT_DEFAULT).strip()
    ordering = _LESSON_SORT_KEYS.get(sort_param) or _LESSON_SORT_KEYS[_LESSON_SORT_DEFAULT]
    if sort_param not in _LESSON_SORT_KEYS:
        sort_param = _LESSON_SORT_DEFAULT
    lessons = course.lessons.order_by(ordering, "id")
    return _render(
        request,
        "teacher_portal/lessons/list.html",
        "lessons",
        {"course": course, "lessons": lessons, "sort_param": sort_param},
    )


@teacher_required
def all_lessons(request):
    qs = teacher_perms.teacher_lesson_queryset(request.user).select_related("course", "course__level")
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    course_id = (request.GET.get("course") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(title_ar__icontains=q) | Q(title_en__icontains=q))
    if status:
        qs = qs.filter(status=status)
    if course_id.isdigit():
        qs = qs.filter(course_id=int(course_id))
    return _render(
        request,
        "teacher_portal/lessons/all.html",
        "lessons",
        {
            "page_obj": _paginate(request, qs.order_by("course__title", "order", "id")),
            "filters": request.GET,
            "courses": teacher_perms.teacher_course_queryset(request.user).only("id", "title", "title_ar"),
        },
    )


@teacher_required
def all_quizzes(request):
    quiz_qs = LessonQuiz.objects.filter(
        lesson__in=teacher_perms.teacher_lesson_queryset(request.user),
    ).select_related("lesson", "lesson__course").annotate(question_count=Count("questions"))
    q = (request.GET.get("q") or "").strip()
    if q:
        quiz_qs = quiz_qs.filter(
            Q(title__icontains=q) | Q(title_ar__icontains=q) | Q(title_en__icontains=q)
            | Q(lesson__title__icontains=q)
        )
    return _render(
        request,
        "teacher_portal/quizzes/all.html",
        "quizzes",
        {
            "page_obj": _paginate(request, quiz_qs.order_by("lesson__course__title", "lesson__order")),
            "filters": request.GET,
        },
    )


@teacher_required
def lesson_create(request, course_id):
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user), pk=course_id)
    if not teacher_perms.teacher_can_edit_course(request.user, course):
        return HttpResponseForbidden("Course is not editable")
    if request.method == "POST":
        form = TeacherLessonForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = lesson_service.create_lesson(request, form, course)
            messages.success(request, "Lesson created.")
            return redirect("teacher_portal:lessons", course_id=course.pk)
    else:
        form = TeacherLessonForm(initial={"cefr_level": course.level.code})
    return _render(request, "teacher_portal/lessons/form.html", "lessons", {"form": form, "course": course, "lesson": None})


@teacher_required
def lesson_edit(request, lesson_id):
    lesson = get_object_or_404(teacher_perms.teacher_lesson_queryset(request.user).select_related("course"), pk=lesson_id)
    if not teacher_perms.teacher_can_edit_lesson(request.user, lesson):
        return HttpResponseForbidden("Only draft or rejected own lessons can be edited")
    if request.method == "POST":
        form = TeacherLessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            lesson = lesson_service.update_lesson(request, form)
            messages.success(request, "Lesson updated.")
            return redirect("teacher_portal:lessons", course_id=lesson.course_id)
    else:
        form = TeacherLessonForm(instance=lesson)
    return _render(request, "teacher_portal/lessons/form.html", "lessons", {"form": form, "course": lesson.course, "lesson": lesson})


@require_POST
@teacher_required
def lesson_submit_review(request, lesson_id):
    lesson = get_object_or_404(teacher_perms.teacher_lesson_queryset(request.user), pk=lesson_id)
    if lesson.status not in {"draft", "rejected"}:
        return HttpResponseForbidden("Lesson cannot be submitted in this status")
    lesson_service.submit_lesson_for_review(request, lesson)
    messages.success(request, "Lesson submitted for review.")
    return redirect("teacher_portal:lessons", course_id=lesson.course_id)


@teacher_required
def lesson_quiz(request, lesson_id):
    lesson = get_object_or_404(teacher_perms.teacher_lesson_queryset(request.user).select_related("course"), pk=lesson_id)
    quiz = getattr(lesson, "quiz", None)
    if request.method == "POST":
        form = TeacherQuizForm(request.POST, instance=quiz)
        if form.is_valid():
            quiz = quiz_service.save_quiz(request, form, lesson)
            messages.success(request, "Quiz saved.")
            return redirect("teacher_portal:quiz_questions", quiz_id=quiz.pk)
    else:
        form = TeacherQuizForm(instance=quiz, initial={"title_en": f"{lesson.title} quiz"})
    return _render(request, "teacher_portal/quizzes/quiz_form.html", "quizzes", {"lesson": lesson, "quiz": quiz, "form": form})


@teacher_required
def quiz_questions(request, quiz_id):
    quiz = get_object_or_404(LessonQuiz.objects.select_related("lesson", "lesson__course"), pk=quiz_id)
    if not teacher_perms.teacher_lesson_queryset(request.user).filter(pk=quiz.lesson_id).exists():
        return HttpResponseForbidden("Forbidden")
    if request.method == "POST":
        form = TeacherQuestionForm(request.POST, user=request.user)
        if form.is_valid():
            quiz_service.save_question(request, form, quiz)
            messages.success(request, "Question saved.")
            return redirect("teacher_portal:quiz_questions", quiz_id=quiz.pk)
    else:
        form = TeacherQuestionForm(user=request.user)
    return _render(
        request,
        "teacher_portal/quizzes/questions.html",
        "quizzes",
        {"quiz": quiz, "questions": quiz.questions.order_by("order", "id"), "form": form},
    )


@teacher_required
def question_edit(request, question_id):
    question = get_object_or_404(LessonQuestion.objects.select_related("quiz", "quiz__lesson"), pk=question_id)
    if not teacher_perms.teacher_lesson_queryset(request.user).filter(pk=question.quiz.lesson_id).exists():
        return HttpResponseForbidden("Forbidden")
    if request.method == "POST":
        form = TeacherQuestionForm(request.POST, instance=question, user=request.user)
        if form.is_valid():
            quiz_service.save_question(request, form, question.quiz)
            messages.success(request, "Question updated.")
            return redirect("teacher_portal:quiz_questions", quiz_id=question.quiz_id)
    else:
        form = TeacherQuestionForm(instance=question, user=request.user)
    return _render(request, "teacher_portal/quizzes/question_edit.html", "quizzes", {"question": question, "quiz": question.quiz, "form": form})


@teacher_required
def students_list(request):
    q = (request.GET.get("q") or "").strip()
    rows = student_service.teacher_student_rows(request.user, search=q)
    return _render(
        request,
        "teacher_portal/students/list.html",
        "students",
        {"page_obj": _paginate(request, rows), "filters": request.GET},
    )


@require_POST
@teacher_required
def issue_certificate(request, student_id, course_id):
    """Teacher issues a completion certificate for one of their students.

    Gated on course ownership + the student having completed every published
    lesson (the eligibility rule). Idempotent.
    """
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user), pk=course_id)
    student = get_object_or_404(get_user_model(), pk=student_id)
    # The student must actually be this teacher's student and enrolled in the
    # course — ownership of the course alone is not enough.
    if not teacher_perms.teacher_can_view_student(request.user, student):
        return HttpResponseForbidden("Forbidden")
    if not CourseEnrollment.objects.filter(user=student, course=course).exists():
        messages.error(request, "This student is not enrolled in that course.")
        return redirect("teacher_portal:student_detail", student_id=student.pk)
    if not DigitalCertificate.is_eligible(student, course):
        messages.error(request, "Student hasn't completed every lesson yet — can't issue a certificate.")
        return redirect("teacher_portal:student_detail", student_id=student.pk)
    cert, created = DigitalCertificate.issue_for(student, course, issued_by=request.user)
    messages.success(request, "Certificate issued." if created else "Certificate already issued.")
    return redirect("teacher_portal:student_detail", student_id=student.pk)


@teacher_required
def student_groups(request):
    """Students grouped by CEFR level — a teaching-community overview."""
    return _render(
        request,
        "teacher_portal/students/groups.html",
        "groups",
        {"groups": student_service.teacher_student_groups(request.user)},
    )


@teacher_required
def student_detail(request, student_id):
    User = get_user_model()
    student = get_object_or_404(User.objects.select_related("profile"), pk=student_id)
    if not teacher_perms.teacher_can_view_student(request.user, student):
        return HttpResponseForbidden("Forbidden")
    context = student_service.teacher_student_detail_context(request.user, student)
    context["note_form"] = TeacherStudentNoteForm(teacher=request.user)
    return _render(request, "teacher_portal/students/detail.html", "students", context)


@require_POST
@teacher_required
def student_note_create(request, student_id):
    User = get_user_model()
    student = get_object_or_404(User, pk=student_id)
    if not teacher_perms.teacher_can_view_student(request.user, student):
        return HttpResponseForbidden("Forbidden")
    form = TeacherStudentNoteForm(request.POST, teacher=request.user)
    if form.is_valid():
        course = form.cleaned_data["course"]
        if not CourseEnrollment.objects.filter(user=student, course=course).exists():
            return HttpResponseForbidden("Student is not enrolled in this course")
        student_service.add_student_note(request, form, student)
        messages.success(request, "Note added.")
    else:
        messages.error(request, "Note could not be saved.")
    return redirect("teacher_portal:student_detail", student_id=student.pk)


@teacher_required
def assignments_list(request):
    assignments = TeacherAssignment.objects.filter(teacher=request.user).select_related("course", "lesson")
    return _render(
        request,
        "teacher_portal/assignments/list.html",
        "assignments",
        {"page_obj": _paginate(request, assignments), "filters": request.GET},
    )


@teacher_required
def assignment_create(request):
    if request.method == "POST":
        form = TeacherAssignmentForm(request.POST, teacher=request.user)
        if form.is_valid():
            assignment = assignment_service.create_assignment(request, form)
            messages.success(request, "Assignment created.")
            return redirect("teacher_portal:assignment_detail", assignment_id=assignment.pk)
    else:
        form = TeacherAssignmentForm(teacher=request.user)
    return _render(request, "teacher_portal/assignments/form.html", "assignments", {"form": form, "assignment": None})


@teacher_required
def assignment_detail(request, assignment_id):
    assignment = get_object_or_404(TeacherAssignment.objects.select_related("course", "lesson"), pk=assignment_id, teacher=request.user)
    return _render(
        request,
        "teacher_portal/assignments/detail.html",
        "assignments",
        {"assignment": assignment, "submissions": assignment.submissions.select_related("student")},
    )


@login_required
def assignment_submit(request, assignment_id):
    assignment = get_object_or_404(TeacherAssignment.objects.select_related("course"), pk=assignment_id, is_active=True)
    if not teacher_perms.student_is_enrolled(request.user, assignment.course):
        return HttpResponseForbidden("Assignment is available only for enrolled students")
    submission = StudentAssignmentSubmission.objects.filter(assignment=assignment, student=request.user).first()
    if request.method == "POST":
        form = StudentAssignmentSubmissionForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            assignment_service.save_submission(request, form, assignment)
            messages.success(request, "Assignment submitted.")
            return redirect("dashboard")
    else:
        form = StudentAssignmentSubmissionForm(instance=submission)
    return _render(request, "teacher_portal/assignments/submit.html", "assignments", {"assignment": assignment, "form": form, "submission": submission})


@teacher_required
def submission_review(request, submission_id):
    submission = get_object_or_404(
        StudentAssignmentSubmission.objects.select_related("assignment", "assignment__teacher", "student"),
        pk=submission_id,
        assignment__teacher=request.user,
    )
    if request.method == "POST":
        form = ReviewSubmissionForm(request.POST, instance=submission)
        if form.is_valid():
            assignment_service.review_submission(request, form)
            messages.success(request, "Submission reviewed.")
            return redirect("teacher_portal:assignment_detail", assignment_id=submission.assignment_id)
    else:
        form = ReviewSubmissionForm(instance=submission)
    return _render(request, "teacher_portal/assignments/review.html", "assignments", {"submission": submission, "form": form})


@teacher_required
def analytics(request):
    return _render(request, "teacher_portal/analytics/overview.html", "analytics", analytics_service.analytics_context(request.user))


TEACHER_NOTIFICATION_EVENT_TYPES = [
    notification_constants.TEACHER_COURSE_APPROVED,
    notification_constants.TEACHER_COURSE_REJECTED,
    notification_constants.TEACHER_ASSIGNMENT_SUBMITTED,
    notification_constants.TEACHER_STUDENT_LOW_PERFORMANCE,
    notification_constants.TEACHER_CONTENT_NEEDS_REVISION,
    notification_constants.TEACHER_DAILY_DIGEST,
]


@teacher_required
def notifications(request):
    events = (
        NotificationEvent.objects
        .filter(user=request.user, event_type__in=TEACHER_NOTIFICATION_EVENT_TYPES)
        .order_by("-created_at")[:50]
    )
    rows = [notification_service.describe_teacher_event(e) for e in events]
    return _render(request, "teacher_portal/notifications/list.html", "notifications", {"rows": rows})


@teacher_required
def settings(request):
    profile, _created = TeacherProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = TeacherProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Teacher settings saved.")
            return redirect("teacher_portal:settings")
    else:
        form = TeacherProfileForm(instance=profile)
    return _render(request, "teacher_portal/settings/profile.html", "settings", {"form": form, "teacher_profile": profile})


@require_POST
@teacher_required
def course_delete(request, pk):
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user), pk=pk)
    if not teacher_perms.teacher_can_edit_course(request.user, course):
        return HttpResponseForbidden("Only draft or rejected courses can be deleted")
    course.delete()
    messages.success(request, "Course deleted.")
    return redirect("teacher_portal:courses")


@require_POST
@teacher_required
def course_archive(request, pk):
    """Soft-delete: flip the course to archived + inactive so it
    disappears from students without losing enrollment data. Allowed
    for published/draft/rejected — anything the teacher owns.
    """
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user), pk=pk)
    course.status = "archived"
    course.is_active = False
    course.save(update_fields=["status", "is_active", "updated_at"])
    messages.success(request, "Course archived.")
    return redirect("teacher_portal:courses")


@require_POST
@teacher_required
def lesson_delete(request, lesson_id):
    lesson = get_object_or_404(teacher_perms.teacher_lesson_queryset(request.user), pk=lesson_id)
    if not teacher_perms.teacher_can_edit_lesson(request.user, lesson):
        return HttpResponseForbidden("Only draft or rejected lessons can be deleted")
    course_id = lesson.course_id
    lesson.delete()
    messages.success(request, "Lesson deleted.")
    return redirect("teacher_portal:lessons", course_id=course_id)


@require_POST
@teacher_required
def quiz_delete(request, quiz_id):
    quiz = get_object_or_404(LessonQuiz.objects.select_related("lesson"), pk=quiz_id)
    if not teacher_perms.teacher_lesson_queryset(request.user).filter(pk=quiz.lesson_id).exists():
        return HttpResponseForbidden("Forbidden")
    lesson_id = quiz.lesson_id
    quiz.delete()
    messages.success(request, "Quiz deleted.")
    return redirect("teacher_portal:lesson_quiz", lesson_id=lesson_id)


@require_POST
@teacher_required
def question_delete(request, question_id):
    question = get_object_or_404(LessonQuestion.objects.select_related("quiz"), pk=question_id)
    if not teacher_perms.teacher_lesson_queryset(request.user).filter(pk=question.quiz.lesson_id).exists():
        return HttpResponseForbidden("Forbidden")
    quiz_id = question.quiz_id
    question.delete()
    messages.success(request, "Question deleted.")
    return redirect("teacher_portal:quiz_questions", quiz_id=quiz_id)


@teacher_required
def live_sessions_list(request):
    """The teacher's scheduled / past live classes."""
    qs = (
        LiveSession.objects.filter(teacher=request.user)
        .select_related("course")
        .order_by("-scheduled_at")
    )
    return _render(
        request,
        "teacher_portal/live_sessions/list.html",
        "live_sessions",
        {"page_obj": _paginate(request, qs), "now": timezone.now()},
    )


@teacher_required
def live_session_create(request):
    """Schedule a live class: generate a Meet link + notify the course's
    students. Enforces the two-per-week-per-course cap via the form."""
    if request.method == "POST":
        form = LiveSessionForm(request.POST, teacher=request.user)
        if form.is_valid():
            session = form.save(commit=False)
            session.teacher = request.user
            session.meet_link = meet_service.generate_meet_link(
                title=session.title,
                start=session.scheduled_at,
                duration_minutes=session.duration_minutes,
            )
            session.save()
            notified = live_session_service.notify_students_scheduled(session)
            messages.success(request, f"Live session scheduled. {notified} student(s) notified.")
            return redirect("teacher_portal:live_sessions")
    else:
        form = LiveSessionForm(teacher=request.user)
    return _render(
        request,
        "teacher_portal/live_sessions/form.html",
        "live_sessions",
        {"form": form},
    )


@require_POST
@teacher_required
def live_session_cancel(request, session_id):
    session = get_object_or_404(LiveSession, pk=session_id, teacher=request.user)
    session.status = "cancelled"
    session.save(update_fields=["status", "updated_at"])
    messages.success(request, "Live session cancelled.")
    return redirect("teacher_portal:live_sessions")


@require_POST
@teacher_required
def assignment_delete(request, assignment_id):
    assignment = get_object_or_404(TeacherAssignment, pk=assignment_id, teacher=request.user)
    assignment.delete()
    messages.success(request, "Assignment deleted.")
    return redirect("teacher_portal:assignments")


@require_POST
@teacher_required
def student_note_delete(request, note_id):
    note = get_object_or_404(TeacherStudentNote, pk=note_id, teacher=request.user)
    student_id = note.student_id
    note.delete()
    messages.success(request, "Note deleted.")
    return redirect("teacher_portal:student_detail", student_id=student_id)
