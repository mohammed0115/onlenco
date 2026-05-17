from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from courses.models import Course, Lesson
from payments.models import PaymentSubmission

from . import permissions as perms
from .decorators import control_login_required, control_permission_required
from .forms import (
    AssignCourseForm,
    CourseAssignTeacherForm,
    CourseRejectForm,
    ExtendSubscriptionForm,
    LessonEditorForm,
    PaymentRejectForm,
    StudentNoteForm,
    StudentNotificationForm,
    StudentRiskForm,
    TeacherAssignCourseForm,
)
from .models import PlatformAuditLog
from .services import (
    ai_monitoring_service,
    analytics_service,
    course_review_service,
    dashboard_service,
    payment_review_service,
    student_management_service,
    teacher_management_service,
)


def _control_context(request, extra=None):
    ctx = {
        "nav_items": perms.nav_items_for(request.user),
        "role_names": sorted(perms.user_role_names(request.user)),
        "is_read_only_admin": perms.is_read_only(request.user),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _render(request, template_name, context=None):
    return render(request, template_name, _control_context(request, context or {}))


def _paginate(request, qs, per_page=25):
    paginator = Paginator(qs, per_page)
    return paginator.get_page(request.GET.get("page") or 1)


@control_permission_required(perms.CAP_DASHBOARD)
def dashboard(request):
    return _render(
        request,
        "platform_admin/dashboard.html",
        {"metrics": dashboard_service.dashboard_metrics_for(request.user), "section": "dashboard"},
    )


@control_permission_required(perms.CAP_STUDENTS_VIEW)
def students_list(request):
    qs = student_management_service.student_queryset_for(request.user, request.GET)
    page = _paginate(request, qs)
    rows = [student_management_service.student_row(student) for student in page.object_list]
    return _render(
        request,
        "platform_admin/students/list.html",
        {"page_obj": page, "rows": rows, "filters": request.GET, "section": "students"},
    )


@control_permission_required(perms.CAP_STUDENTS_VIEW)
def student_detail(request, pk):
    User = get_user_model()
    student = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    if not perms.can_view_student(request.user, student):
        return HttpResponseForbidden("Forbidden")
    context = student_management_service.student_detail_context(student)
    context.update({
        "note_form": StudentNoteForm(),
        "notification_form": StudentNotificationForm(),
        "risk_form": StudentRiskForm(initial={"risk_status": context["flag"].risk_status}),
        "assign_course_form": AssignCourseForm(course_queryset=perms.courses_for_user(request.user, Course.objects.filter(status__in=["published", "draft", "pending_review"]))),
        "extend_form": ExtendSubscriptionForm(),
        "section": "students",
    })
    return _render(request, "platform_admin/students/detail.html", context)


@require_POST
@control_permission_required(perms.CAP_STUDENTS_VIEW)
def student_action(request, pk, action):
    User = get_user_model()
    student = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    if not perms.can_view_student(request.user, student):
        return HttpResponseForbidden("Forbidden")

    if action == "reset-placement":
        if not perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE):
            return HttpResponseForbidden("Forbidden")
        student_management_service.reset_placement(request, student)
        messages.success(request, "Placement reset.")
    elif action == "mark-risk":
        if not (
            perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE)
            or perms.has_capability(request.user, perms.CAP_NOTIFICATIONS_MANAGE)
        ):
            return HttpResponseForbidden("Forbidden")
        form = StudentRiskForm(request.POST)
        if form.is_valid():
            student_management_service.mark_risk(request, student, form.cleaned_data["risk_status"])
            messages.success(request, "Risk status updated.")
        else:
            messages.error(request, "Invalid risk status.")
    elif action == "deactivate":
        if not perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE):
            return HttpResponseForbidden("Forbidden")
        student_management_service.deactivate_student(request, student)
        messages.warning(request, "Student account deactivated.")
    elif action == "add-note":
        if not (
            perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE)
            or perms.has_capability(request.user, perms.CAP_NOTIFICATIONS_MANAGE)
        ):
            return HttpResponseForbidden("Forbidden")
        form = StudentNoteForm(request.POST)
        if form.is_valid():
            student_management_service.add_note(
                request,
                student,
                form.cleaned_data["note"],
                form.cleaned_data["is_private"],
            )
            messages.success(request, "Note added.")
        else:
            messages.error(request, "Note is required.")
    elif action == "assign-course":
        if not perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE):
            return HttpResponseForbidden("Forbidden")
        form = AssignCourseForm(request.POST, course_queryset=perms.courses_for_user(request.user, Course.objects.all()))
        if form.is_valid():
            student_management_service.assign_course(request, student, form.cleaned_data["course"])
            messages.success(request, "Course assigned.")
        else:
            messages.error(request, "Choose a valid course.")
    elif action == "send-notification":
        if not (
            perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE)
            or perms.has_capability(request.user, perms.CAP_NOTIFICATIONS_MANAGE)
        ):
            return HttpResponseForbidden("Forbidden")
        form = StudentNotificationForm(request.POST)
        if form.is_valid():
            student_management_service.send_notification(
                request,
                student,
                form.cleaned_data["title"],
                form.cleaned_data["message"],
            )
            messages.success(request, "Notification queued.")
        else:
            messages.error(request, "Notification title and message are required.")
    elif action == "extend-subscription":
        if not perms.can_manage_payment(request.user):
            return HttpResponseForbidden("Forbidden")
        form = ExtendSubscriptionForm(request.POST)
        if form.is_valid():
            payment_review_service.extend_subscription(request, student, form.cleaned_data["days"])
            messages.success(request, "Subscription extended.")
        else:
            messages.error(request, "Invalid subscription duration.")
    else:
        raise Http404("Unknown action")
    return redirect("platform_admin:student_detail", pk=student.pk)


@control_permission_required(perms.CAP_TEACHERS_VIEW)
def teachers_list(request):
    qs = teacher_management_service.teacher_queryset(request.GET)
    page = _paginate(request, qs)
    return _render(
        request,
        "platform_admin/teachers/list.html",
        {"page_obj": page, "filters": request.GET, "section": "teachers"},
    )


@control_permission_required(perms.CAP_TEACHERS_VIEW)
def teacher_detail(request, pk):
    User = get_user_model()
    teacher = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    context = teacher_management_service.teacher_detail_context(teacher)
    context.update({"assign_form": TeacherAssignCourseForm(), "section": "teachers"})
    return _render(request, "platform_admin/teachers/detail.html", context)


@require_POST
@control_permission_required(perms.CAP_TEACHERS_MANAGE)
def teacher_action(request, pk, action):
    User = get_user_model()
    teacher = get_object_or_404(User, pk=pk)
    if action == "assign-course":
        form = TeacherAssignCourseForm(request.POST)
        if form.is_valid():
            teacher_management_service.assign_course_to_teacher(request, teacher, form.cleaned_data["course"])
            messages.success(request, "Course assigned to teacher.")
        else:
            messages.error(request, "Choose a valid course.")
    elif action == "deactivate":
        teacher_management_service.deactivate_teacher(request, teacher)
        messages.warning(request, "Teacher account deactivated.")
    elif action == "assign-role":
        teacher_management_service.assign_teacher_role(request, teacher)
        messages.success(request, "Teacher role assigned.")
    elif action == "remove-role":
        teacher_management_service.remove_teacher_role(request, teacher)
        messages.warning(request, "Teacher role removed.")
    else:
        raise Http404("Unknown action")
    return redirect("platform_admin:teacher_detail", pk=teacher.pk)


@control_permission_required(perms.CAP_COURSES_VIEW)
def courses_list(request):
    qs = course_review_service.course_queryset_for(request.user, request.GET)
    page = _paginate(request, qs)
    return _render(
        request,
        "platform_admin/courses/list.html",
        {"page_obj": page, "filters": request.GET, "section": "courses"},
    )


@control_permission_required(perms.CAP_COURSES_VIEW)
def course_detail(request, pk):
    course = get_object_or_404(course_review_service.course_queryset_for(request.user), pk=pk)
    context = course_review_service.course_detail_context(course)
    context.update({
        "reject_form": CourseRejectForm(),
        "assign_teacher_form": CourseAssignTeacherForm(),
        "can_manage_course": perms.can_manage_course(request.user, course),
        "can_review_course": perms.can_review_course(request.user),
        "section": "courses",
    })
    return _render(request, "platform_admin/courses/detail.html", context)


@control_permission_required(perms.CAP_COURSES_REVIEW)
def courses_review(request):
    qs = course_review_service.pending_review_queryset_for(request.user)
    return _render(
        request,
        "platform_admin/courses/review.html",
        {"courses": qs, "reject_form": CourseRejectForm(), "section": "courses"},
    )


@require_POST
@control_permission_required(perms.CAP_COURSES_REVIEW)
def course_action(request, pk, action):
    course = get_object_or_404(course_review_service.course_queryset_for(request.user), pk=pk)
    if action == "approve":
        course_review_service.approve_course(request, course)
        messages.success(request, "Course approved and published.")
    elif action == "reject":
        form = CourseRejectForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Rejection notes are required.")
            return redirect("platform_admin:course_detail", pk=course.pk)
        course_review_service.reject_course(request, course, form.cleaned_data["notes"])
        messages.warning(request, "Course rejected.")
    elif action == "publish":
        course_review_service.publish_course(request, course)
        messages.success(request, "Course published.")
    elif action == "archive":
        course_review_service.archive_course(request, course)
        messages.warning(request, "Course archived.")
    elif action == "assign-teacher":
        form = CourseAssignTeacherForm(request.POST)
        if form.is_valid():
            teacher_management_service.assign_course_to_teacher(request, form.cleaned_data["teacher"], course)
            messages.success(request, "Teacher assigned.")
        else:
            messages.error(request, "Choose a valid teacher.")
    else:
        raise Http404("Unknown action")
    return redirect("platform_admin:course_detail", pk=course.pk)


@control_permission_required(perms.CAP_COURSES_MANAGE)
def lesson_editor(request, course_pk, lesson_pk=None):
    course = get_object_or_404(course_review_service.course_queryset_for(request.user), pk=course_pk)
    if not perms.can_manage_course(request.user, course):
        return HttpResponseForbidden("Forbidden")
    lesson = None
    if lesson_pk is not None:
        lesson = get_object_or_404(Lesson.objects.filter(course=course), pk=lesson_pk)

    if request.method == "POST":
        form = LessonEditorForm(
            request.POST,
            request.FILES,
            instance=lesson,
            course=course,
            can_review=perms.can_review_course(request.user),
        )
        if form.is_valid():
            saved = course_review_service.save_lesson_with_worksheet(request, form, course=course, lesson=lesson)
            messages.success(request, "Lesson saved.")
            return redirect("platform_admin:course_detail", pk=saved.course_id)
    else:
        form = LessonEditorForm(instance=lesson, course=course, can_review=perms.can_review_course(request.user))
    return _render(
        request,
        "platform_admin/courses/lesson_editor.html",
        {"course": course, "lesson": lesson, "form": form, "section": "courses"},
    )


@control_permission_required(perms.CAP_PAYMENTS_VIEW)
def payments_list(request):
    qs = payment_review_service.payment_queryset(request.GET)
    page = _paginate(request, qs)
    return _render(
        request,
        "platform_admin/payments/list.html",
        {"page_obj": page, "metrics": payment_review_service.payment_metrics(), "filters": request.GET, "section": "payments"},
    )


@control_permission_required(perms.CAP_PAYMENTS_VIEW)
def payment_detail(request, pk):
    payment = get_object_or_404(PaymentSubmission.objects.select_related("user", "user__profile", "reviewed_by"), pk=pk)
    return _render(
        request,
        "platform_admin/payments/detail.html",
        {"payment": payment, "reject_form": PaymentRejectForm(), "extend_form": ExtendSubscriptionForm(), "section": "payments"},
    )


@require_POST
@control_permission_required(perms.CAP_PAYMENTS_MANAGE)
def payment_action(request, pk, action):
    payment = get_object_or_404(PaymentSubmission.objects.select_related("user", "user__profile"), pk=pk)
    if action == "approve":
        payment_review_service.approve_payment(request, payment)
        messages.success(request, "Payment approved.")
    elif action == "reject":
        form = PaymentRejectForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Rejection reason is required.")
            return redirect("platform_admin:payment_detail", pk=payment.pk)
        payment_review_service.reject_payment(request, payment, form.cleaned_data["reason"])
        messages.warning(request, "Payment rejected.")
    elif action == "extend-subscription":
        form = ExtendSubscriptionForm(request.POST)
        if form.is_valid():
            payment_review_service.extend_subscription(request, payment.user, form.cleaned_data["days"])
            messages.success(request, "Subscription extended.")
        else:
            messages.error(request, "Invalid duration.")
    elif action == "expire-subscription":
        payment_review_service.expire_subscription(request, payment.user)
        messages.warning(request, "Subscription expired.")
    else:
        raise Http404("Unknown action")
    return redirect("platform_admin:payment_detail", pk=payment.pk)


@control_permission_required(perms.CAP_PAYMENTS_VIEW)
def payment_proof(request, pk):
    payment = get_object_or_404(PaymentSubmission, pk=pk)
    if not payment.screenshot:
        raise Http404("Payment proof not found")
    try:
        return FileResponse(
            payment.screenshot.open("rb"),
            as_attachment=True,
            filename=payment.screenshot.name.rsplit("/", 1)[-1],
        )
    except FileNotFoundError:
        raise Http404("Payment proof not found")


@control_permission_required(perms.CAP_AI_VIEW)
def ai_overview(request):
    return _render(
        request,
        "platform_admin/ai/overview.html",
        {"metrics": ai_monitoring_service.ai_overview_metrics(), "readiness": ai_monitoring_service.readiness_report(), "section": "ai"},
    )


@control_permission_required(perms.CAP_AI_VIEW)
def ai_tutor_logs(request):
    return _render(
        request,
        "platform_admin/ai/tutor_logs.html",
        {"logs": ai_monitoring_service.tutor_logs(request.GET), "filters": request.GET, "section": "ai"},
    )


@control_permission_required(perms.CAP_AI_VIEW)
def ai_dataset_review(request):
    return _render(
        request,
        "platform_admin/ai/dataset_review.html",
        {**ai_monitoring_service.dataset_review_context(), "section": "ai"},
    )


@require_POST
@control_permission_required(perms.CAP_AI_MANAGE)
def ai_dataset_action(request, action):
    try:
        from ai_training.models import AITrainingExample
    except Exception:
        raise Http404("AI training app unavailable")
    example = get_object_or_404(AITrainingExample, pk=request.POST.get("example_id"))
    if action == "approve":
        ai_monitoring_service.approve_training_example(request, example)
        messages.success(request, "Training example approved.")
    elif action == "reject":
        ai_monitoring_service.reject_training_example(request, example)
        messages.warning(request, "Training example rejected.")
    else:
        raise Http404("Unknown action")
    return redirect("platform_admin:ai_datasets")


@control_permission_required(perms.CAP_AI_VIEW)
def ai_model_metrics(request):
    return _render(
        request,
        "platform_admin/ai/model_metrics.html",
        {**ai_monitoring_service.model_metrics_context(), "section": "ai"},
    )


@control_permission_required(perms.CAP_ANALYTICS_VIEW)
def analytics_overview(request):
    return _render(
        request,
        "platform_admin/analytics/overview.html",
        {"analytics": analytics_service.analytics_overview(), "section": "analytics"},
    )


@control_permission_required(perms.CAP_ANALYTICS_VIEW)
def analytics_learning(request):
    return _render(
        request,
        "platform_admin/analytics/learning.html",
        {"learning": analytics_service.learning_analytics(), "section": "analytics"},
    )


@control_permission_required(perms.CAP_ANALYTICS_VIEW)
def analytics_payments(request):
    return _render(
        request,
        "platform_admin/analytics/payments.html",
        {"financial": analytics_service.financial_analytics(), "section": "analytics"},
    )


@control_permission_required(perms.CAP_ANALYTICS_VIEW)
def analytics_retention(request):
    return _render(
        request,
        "platform_admin/analytics/retention.html",
        {"engagement": analytics_service.engagement_analytics(), "section": "analytics"},
    )


@control_permission_required(perms.CAP_SETTINGS_VIEW)
def settings_roles(request):
    return _render(
        request,
        "platform_admin/settings/roles.html",
        {"roles": perms.ROLE_CAPABILITIES, "section": "settings"},
    )


@control_permission_required(perms.CAP_NOTIFICATIONS_MANAGE)
def settings_notifications(request):
    try:
        from notifications.models import EmailNotification, NotificationTemplate
        emails = EmailNotification.objects.order_by("-created_at")[:50]
        templates = NotificationTemplate.objects.order_by("event_type", "language")
    except Exception:
        emails = []
        templates = []
    return _render(
        request,
        "platform_admin/settings/notifications.html",
        {"emails": emails, "templates": templates, "section": "settings"},
    )


@control_permission_required(perms.CAP_SETTINGS_VIEW)
def settings_platform(request):
    return _render(request, "platform_admin/settings/platform.html", {"section": "settings"})


@control_permission_required(perms.CAP_GAMIFICATION_MANAGE)
def settings_gamification(request):
    try:
        from motivation.models import Achievement, Challenge, UserBadge
        achievements = Achievement.objects.order_by("category", "threshold_value")[:50]
        challenges = Challenge.objects.order_by("-start_at")[:50]
        badges_count = UserBadge.objects.count()
    except Exception:
        achievements = []
        challenges = []
        badges_count = 0
    return _render(
        request,
        "platform_admin/settings/gamification.html",
        {"achievements": achievements, "challenges": challenges, "badges_count": badges_count, "section": "settings"},
    )


@control_permission_required(perms.CAP_AUDIT_VIEW)
def audit_logs(request):
    qs = PlatformAuditLog.objects.select_related("actor", "target_user").all()
    action = (request.GET.get("action") or "").strip()
    if action:
        qs = qs.filter(action_type__icontains=action)
    page = _paginate(request, qs, per_page=40)
    return _render(
        request,
        "platform_admin/audit_logs.html",
        {"page_obj": page, "filters": request.GET, "section": "audit"},
    )
