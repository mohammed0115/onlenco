from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from courses.models import Course, CourseEnrollment, Lesson, LessonQuestion, LessonQuiz
from notifications.models import NotificationEvent

from . import permissions as teacher_perms
from .forms import (
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
from .models import StudentAssignmentSubmission, TeacherAssignment, TeacherProfile
from .permissions import teacher_required
from .services import (
    analytics_service,
    assignment_service,
    course_service,
    dashboard_service,
    lesson_service,
    quiz_service,
    student_service,
)
from .services.role_service import ROLE_STUDENT, ROLE_TEACHER, RoleService


def _teacher_nav():
    return [
        ("dashboard", "layout-dashboard", "Teacher Dashboard", "لوحة المعلم", "teacher_portal:dashboard"),
        ("courses", "book-open", "My Courses", "كورساتي", "teacher_portal:courses"),
        ("lessons", "play-square", "My Lessons", "دروسي", "teacher_portal:courses"),
        ("quizzes", "list-checks", "Quizzes", "اختباراتي", "teacher_portal:courses"),
        ("students", "users", "My Students", "طلابي", "teacher_portal:students"),
        ("assignments", "clipboard-list", "Assignments", "الواجبات", "teacher_portal:assignments"),
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


@teacher_required
def dashboard(request):
    return _render(
        request,
        "teacher_portal/dashboard.html",
        "dashboard",
        dashboard_service.dashboard_context(request.user),
    )


@teacher_required
def courses_list(request):
    qs = teacher_perms.teacher_course_queryset(request.user).select_related("level").prefetch_related("lessons", "enrollments")
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
    return _render(
        request,
        "teacher_portal/courses/list.html",
        "courses",
        {"page_obj": _paginate(request, qs), "filters": request.GET},
    )


@teacher_required
def course_detail(request, pk):
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user).select_related("level", "teacher"), pk=pk)
    return _render(
        request,
        "teacher_portal/courses/detail.html",
        "courses",
        {
            "course": course,
            "lessons": course.lessons.order_by("order", "id"),
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


@teacher_required
def lessons_list(request, course_id):
    course = get_object_or_404(teacher_perms.teacher_course_queryset(request.user), pk=course_id)
    lessons = course.lessons.order_by("order", "id")
    return _render(request, "teacher_portal/lessons/list.html", "lessons", {"course": course, "lessons": lessons})


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
        form = TeacherQuestionForm(request.POST)
        if form.is_valid():
            quiz_service.save_question(request, form, quiz)
            messages.success(request, "Question saved.")
            return redirect("teacher_portal:quiz_questions", quiz_id=quiz.pk)
    else:
        form = TeacherQuestionForm()
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
        form = TeacherQuestionForm(request.POST, instance=question)
        if form.is_valid():
            quiz_service.save_question(request, form, question.quiz)
            messages.success(request, "Question updated.")
            return redirect("teacher_portal:quiz_questions", quiz_id=question.quiz_id)
    else:
        form = TeacherQuestionForm(instance=question)
    return _render(request, "teacher_portal/quizzes/question_edit.html", "quizzes", {"question": question, "form": form})


@teacher_required
def students_list(request):
    rows = student_service.teacher_student_rows(request.user)
    q = (request.GET.get("q") or "").strip().lower()
    if q:
        rows = [
            row for row in rows
            if q in (row["student"].email or "").lower()
            or q in (row["student"].username or "").lower()
            or q in (getattr(row["student"].profile, "full_name", "") or "").lower()
        ]
    return _render(request, "teacher_portal/students/list.html", "students", {"rows": rows, "filters": request.GET})


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
    return _render(request, "teacher_portal/assignments/list.html", "assignments", {"assignments": assignments})


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


@teacher_required
def notifications(request):
    events = NotificationEvent.objects.filter(user=request.user).order_by("-created_at")[:50]
    return _render(request, "teacher_portal/notifications/list.html", "notifications", {"events": events})


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
