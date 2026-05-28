from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from courses.models import Course, Lesson
from payments.models import PaymentSubmission

logger = logging.getLogger(__name__)

from . import permissions as perms
from .decorators import control_login_required, control_permission_required
from .forms import (
    AssignCourseForm,
    CourseAssignTeacherForm,
    CourseRejectForm,
    ExtendSubscriptionForm,
    LessonEditorForm,
    PaymentMethodAccountForm,
    PaymentRefundForm,
    PaymentRejectForm,
    PlacementQuestionForm,
    RegisterTeacherForm,
    StudentNoteForm,
    StudentNotificationForm,
    StudentRiskForm,
    SubscriptionPlanForm,
    TeacherAssignCourseForm,
)
from subscriptions.models import AvatarProfile, SubscriptionPlan, VoiceProfile
from .models import PlatformAuditLog
from .services import (
    ai_monitoring_service,
    analytics_service,
    course_review_service,
    dashboard_service,
    payment_review_service,
    role_dashboards,
    student_management_service,
    teacher_management_service,
)


def _control_context(request, extra=None):
    try:
        from teacher_portal.services.role_service import RoleService
        can_access_teacher_portal = RoleService.is_teacher_user(request.user)
    except Exception:
        can_access_teacher_portal = False
    ctx = {
        "nav_items": perms.nav_items_for(request.user),
        "role_names": sorted(perms.user_role_names(request.user)),
        "is_read_only_admin": perms.is_read_only(request.user),
        "can_access_teacher_portal": can_access_teacher_portal,
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
    target = role_dashboards.dashboard_url_for(request.user)
    if target != "platform_admin:dashboard":
        return redirect(target)
    return _render(
        request,
        "platform_admin/dashboard.html",
        {"metrics": dashboard_service.dashboard_metrics_for(request.user), "section": "dashboard"},
    )


@control_permission_required(perms.CAP_DASHBOARD)
def dashboard_academic(request):
    if not perms.has_role(
        request.user,
        perms.GROUP_ACADEMIC_ADMIN,
        perms.GROUP_PLATFORM_ADMIN,
        perms.GROUP_SUPER_ADMIN,
    ):
        return HttpResponseForbidden("Academic admin access required")
    return _render(
        request,
        "platform_admin/dashboards/academic.html",
        {"section": "dashboard", **role_dashboards.academic_dashboard_context()},
    )


@control_permission_required(perms.CAP_DASHBOARD)
def dashboard_finance(request):
    if not perms.has_capability(request.user, perms.CAP_PAYMENTS_VIEW):
        return HttpResponseForbidden("Finance access required")
    return _render(
        request,
        "platform_admin/dashboards/finance.html",
        {"section": "dashboard", **role_dashboards.finance_dashboard_context()},
    )


@control_permission_required(perms.CAP_DASHBOARD)
def dashboard_support(request):
    if not perms.has_capability(request.user, perms.CAP_STUDENTS_VIEW):
        return HttpResponseForbidden("Support access required")
    return _render(
        request,
        "platform_admin/dashboards/support.html",
        {"section": "dashboard", **role_dashboards.support_dashboard_context()},
    )


@control_permission_required(perms.CAP_DASHBOARD)
def dashboard_ai(request):
    if not perms.has_capability(request.user, perms.CAP_AI_VIEW):
        return HttpResponseForbidden("AI admin access required")
    return _render(
        request,
        "platform_admin/dashboards/ai.html",
        {"section": "dashboard", **role_dashboards.ai_dashboard_context()},
    )


@control_permission_required(perms.CAP_DASHBOARD)
def dashboard_readonly(request):
    return _render(
        request,
        "platform_admin/dashboards/readonly.html",
        {"section": "dashboard", "metrics": role_dashboards.readonly_dashboard_context(request.user)},
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
    elif action == "verify-email":
        # Support workaround for users who never receive the verification
        # email (Gmail spam-filter, throw-away inbox, etc.).
        if not (
            perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE)
            or perms.has_capability(request.user, perms.CAP_NOTIFICATIONS_MANAGE)
        ):
            return HttpResponseForbidden("Forbidden")
        profile = getattr(student, "profile", None)
        if profile is None or profile.email_verified:
            messages.info(request, "Email is already verified.")
        else:
            profile.email_verified = True
            profile.save(update_fields=["email_verified"])
            from .services.audit_log_service import log_action
            log_action(
                request,
                action_type="student.email_verify_manual",
                target_user=student,
                description=f"Manually marked email verified for {student.email or student.username}",
            )
            messages.success(request, "Email marked as verified.")
    elif action == "resend-verification":
        if not (
            perms.can_mutate(request.user, perms.CAP_STUDENTS_MANAGE)
            or perms.has_capability(request.user, perms.CAP_NOTIFICATIONS_MANAGE)
        ):
            return HttpResponseForbidden("Forbidden")
        if not student.email:
            messages.error(request, "Student has no email on file.")
        else:
            try:
                from notifications.services import issue_verification_token
                token = issue_verification_token(student)
                from .services.audit_log_service import log_action
                log_action(
                    request,
                    action_type="student.verification_resend",
                    target_user=student,
                    description=f"Resent verification email to {student.email}",
                    metadata={"code_id": getattr(token, "pk", None)},
                )
                messages.success(request, f"Verification email resent to {student.email}.")
            except Exception:
                logger.exception("resend verification failed for %s", student.pk)
                messages.error(request, "Failed to resend verification email — check server logs.")
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


@control_permission_required(perms.CAP_TEACHERS_MANAGE)
def teacher_create(request):
    if not perms.can_mutate(request.user, perms.CAP_TEACHERS_MANAGE):
        return HttpResponseForbidden("Teacher management required")
    if request.method == "POST":
        form = RegisterTeacherForm(request.POST)
        if form.is_valid():
            user, temp_password = teacher_management_service.register_teacher(
                request,
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                email=form.cleaned_data["email"],
            )
            email_sent = teacher_management_service.send_teacher_welcome_email(user, temp_password)
            if email_sent:
                messages.success(
                    request,
                    f"Teacher {user.email} created. A temporary password was emailed.",
                )
            else:
                messages.warning(
                    request,
                    f"Teacher {user.email} created, but the welcome email failed. "
                    f"Temporary password: {temp_password}",
                )
            return redirect("platform_admin:teacher_detail", pk=user.pk)
    else:
        form = RegisterTeacherForm()
    return _render(
        request,
        "platform_admin/teachers/create.html",
        {"form": form, "section": "teachers"},
    )


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
        {
            "page_obj": page,
            "filters": request.GET,
            "section": "courses",
            "sort_cols": course_review_service.course_sort_headers(request.GET),
        },
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
        {
            "payment": payment,
            "reject_form": PaymentRejectForm(),
            "refund_form": PaymentRefundForm(),
            "extend_form": ExtendSubscriptionForm(),
            "section": "payments",
        },
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
    elif action == "refund":
        if payment.status != "approved":
            messages.error(request, "Only an approved payment can be refunded.")
            return redirect("platform_admin:payment_detail", pk=payment.pk)
        form = PaymentRefundForm(request.POST)
        if not form.is_valid():
            messages.error(request, "A refund reason is required.")
            return redirect("platform_admin:payment_detail", pk=payment.pk)
        payment_review_service.refund_payment(request, payment, form.cleaned_data["reason"])
        messages.warning(request, "Payment refunded and subscription revoked.")
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


@control_permission_required(perms.CAP_PAYMENTS_VIEW)
def payments_export(request):
    """Stream the current (filtered) payment list as a CSV download —
    a transaction record for finance reconciliation."""
    import csv

    qs = payment_review_service.payment_queryset(request.GET)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="onlenco-payments.csv"'
    # UTF-8 BOM so Excel renders Arabic student names correctly.
    response.write("﻿")
    writer = csv.writer(response)
    writer.writerow([
        "ID", "Student", "Email", "Plan", "Method", "Amount SDG",
        "Status", "Reference", "Submitted", "Reviewed", "Reviewed by",
    ])
    for p in qs.iterator():
        profile = getattr(p.user, "profile", None)
        writer.writerow([
            p.pk,
            getattr(profile, "full_name", "") or "",
            p.user.email or p.user.username,
            p.plan, p.method, p.amount_sdg, p.status,
            p.transaction_reference,
            p.submitted_at.strftime("%Y-%m-%d %H:%M") if p.submitted_at else "",
            p.reviewed_at.strftime("%Y-%m-%d %H:%M") if p.reviewed_at else "",
            (p.reviewed_by.email or p.reviewed_by.username) if p.reviewed_by else "",
        ])
    return response


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


# ---------------------------------------------------------------------------
# Subscription plans (Sprint 1)
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_PLANS_VIEW)
def plans_list(request):
    plans = SubscriptionPlan.objects.all().order_by("sort_order", "ai_tutor_daily_minutes")
    return _render(
        request,
        "platform_admin/plans/list.html",
        {"plans": plans, "section": "plans"},
    )


@control_permission_required(perms.CAP_PLANS_MANAGE)
def plan_create(request):
    if not perms.can_mutate(request.user, perms.CAP_PLANS_MANAGE):
        return HttpResponseForbidden("Plan management required")
    if request.method == "POST":
        form = SubscriptionPlanForm(request.POST)
        if form.is_valid():
            plan = form.save()
            from .services.audit_log_service import log_action
            log_action(
                request,
                action_type="plan.create",
                object_type="SubscriptionPlan",
                object_id=plan.pk,
                description=f"Created subscription plan '{plan.code}'",
                metadata={
                    "price_sdg": plan.price_sdg,
                    "ai_tutor_daily_minutes": plan.ai_tutor_daily_minutes,
                },
            )
            messages.success(request, f"Plan '{plan.code}' created.")
            return redirect("platform_admin:plans")
    else:
        form = SubscriptionPlanForm()
    return _render(
        request,
        "platform_admin/plans/form.html",
        {"form": form, "plan": None, "section": "plans"},
    )


@control_permission_required(perms.CAP_PLANS_MANAGE)
def plan_edit(request, pk):
    if not perms.can_mutate(request.user, perms.CAP_PLANS_MANAGE):
        return HttpResponseForbidden("Plan management required")
    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    if request.method == "POST":
        form = SubscriptionPlanForm(request.POST, instance=plan)
        if form.is_valid():
            plan = form.save()
            from .services.audit_log_service import log_action
            log_action(
                request,
                action_type="plan.update",
                object_type="SubscriptionPlan",
                object_id=plan.pk,
                description=f"Updated subscription plan '{plan.code}'",
                metadata={
                    "price_sdg": plan.price_sdg,
                    "ai_tutor_daily_minutes": plan.ai_tutor_daily_minutes,
                },
            )
            messages.success(request, f"Plan '{plan.code}' updated.")
            return redirect("platform_admin:plans")
    else:
        form = SubscriptionPlanForm(instance=plan)
    return _render(
        request,
        "platform_admin/plans/form.html",
        {"form": form, "plan": plan, "section": "plans"},
    )


@require_POST
@control_permission_required(perms.CAP_PLANS_MANAGE)
def plan_delete(request, pk):
    if not perms.can_mutate(request.user, perms.CAP_PLANS_MANAGE):
        return HttpResponseForbidden("Plan management required")
    plan = get_object_or_404(SubscriptionPlan, pk=pk)
    if plan.subscriptions.exists():
        messages.error(
            request,
            f"Cannot delete '{plan.code}' — it has existing subscriptions. "
            f"Deactivate it instead.",
        )
        return redirect("platform_admin:plans")
    code = plan.code
    plan.delete()
    from .services.audit_log_service import log_action
    log_action(
        request,
        action_type="plan.delete",
        object_type="SubscriptionPlan",
        object_id=pk,
        description=f"Deleted subscription plan '{code}'",
    )
    messages.success(request, f"Plan '{code}' deleted.")
    return redirect("platform_admin:plans")


# ---------------------------------------------------------------------------
# Voices & Avatars catalogue (Sprint 3)
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_SETTINGS_VIEW)
def voices_list(request):
    voices = VoiceProfile.objects.all().order_by("sort_order", "name_en")
    avatars = AvatarProfile.objects.all().order_by("sort_order", "name_en")
    return _render(
        request,
        "platform_admin/voices/list.html",
        {"voices": voices, "avatars": avatars, "section": "voices"},
    )


@require_POST
@control_permission_required(perms.CAP_SETTINGS_MANAGE)
def voice_toggle_active(request, pk):
    if not perms.can_mutate(request.user, perms.CAP_SETTINGS_MANAGE):
        return HttpResponseForbidden("Settings management required")
    voice = get_object_or_404(VoiceProfile, pk=pk)
    voice.is_active = not voice.is_active
    voice.save(update_fields=["is_active", "updated_at"])
    from .services.audit_log_service import log_action
    log_action(
        request,
        action_type="voice.toggle_active",
        object_type="VoiceProfile",
        object_id=voice.pk,
        description=f"Voice '{voice.code}' is_active → {voice.is_active}",
    )
    messages.success(request, f"Voice '{voice.code}' updated.")
    return redirect("platform_admin:voices")


@require_POST
@control_permission_required(perms.CAP_SETTINGS_MANAGE)
def avatar_toggle_active(request, pk):
    if not perms.can_mutate(request.user, perms.CAP_SETTINGS_MANAGE):
        return HttpResponseForbidden("Settings management required")
    avatar = get_object_or_404(AvatarProfile, pk=pk)
    avatar.is_active = not avatar.is_active
    avatar.save(update_fields=["is_active", "updated_at"])
    from .services.audit_log_service import log_action
    log_action(
        request,
        action_type="avatar.toggle_active",
        object_type="AvatarProfile",
        object_id=avatar.pk,
        description=f"Avatar '{avatar.code}' is_active → {avatar.is_active}",
    )
    messages.success(request, f"Avatar '{avatar.code}' updated.")
    return redirect("platform_admin:voices")


# ---------------------------------------------------------------------------
# Gamification sounds (Sprint 5)
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_GAMIFICATION_MANAGE)
def gamification_sounds(request):
    """List + inline-edit the GameEventSound catalogue."""
    from motivation.models import GameEventSound
    from django import forms

    class SoundForm(forms.ModelForm):
        class Meta:
            model = GameEventSound
            fields = [
                "code", "audio_url", "fallback_audio_path",
                "message_en", "message_ar",
                "animation", "xp_callout_template_en", "xp_callout_template_ar",
                "is_active",
            ]

    if request.method == "POST":
        if not perms.can_mutate(request.user, perms.CAP_GAMIFICATION_MANAGE):
            return HttpResponseForbidden("Gamification management required")
        sound_id = request.POST.get("sound_id")
        if sound_id:
            sound = get_object_or_404(GameEventSound, pk=sound_id)
            form = SoundForm(request.POST, instance=sound)
            if form.is_valid():
                form.save()
                from .services.audit_log_service import log_action
                log_action(
                    request,
                    action_type="game_event_sound.update",
                    object_type="GameEventSound",
                    object_id=sound.pk,
                    description=f"Updated sound '{sound.code}'",
                )
                messages.success(request, f"Sound '{sound.code}' updated.")
        return redirect("platform_admin:gamification_sounds")

    sounds = GameEventSound.objects.all().order_by("code")
    forms_for_sounds = [(s, SoundForm(instance=s)) for s in sounds]
    return _render(
        request,
        "platform_admin/gamification/sounds.html",
        {"sound_forms": forms_for_sounds, "section": "settings"},
    )


@control_permission_required(perms.CAP_SETTINGS_MANAGE)
def avatar_upload_image(request, pk):
    """Upload a real photo for an AvatarProfile.

    The Sprint 3 seed shipped placeholder avatars without images. Admins
    use this form to attach a real face — used by the voice-call screen
    as the talking head.
    """
    if not perms.can_mutate(request.user, perms.CAP_SETTINGS_MANAGE):
        return HttpResponseForbidden("Settings management required")
    avatar = get_object_or_404(AvatarProfile, pk=pk)
    if request.method == "POST":
        uploaded = request.FILES.get("image_file")
        image_url = (request.POST.get("image_url") or "").strip()
        if uploaded:
            avatar.image_file = uploaded
            avatar.save(update_fields=["image_file", "updated_at"])
            from .services.audit_log_service import log_action
            log_action(
                request,
                action_type="avatar.image_upload",
                object_type="AvatarProfile",
                object_id=avatar.pk,
                description=f"Uploaded image for avatar '{avatar.code}'",
            )
            messages.success(request, f"Image uploaded for '{avatar.code}'.")
        elif image_url:
            avatar.image_url = image_url
            avatar.save(update_fields=["image_url", "updated_at"])
            messages.success(request, f"Image URL saved for '{avatar.code}'.")
        else:
            messages.error(request, "Provide either a file or a URL.")
        return redirect("platform_admin:voices")
    return _render(
        request,
        "platform_admin/voices/avatar_image_upload.html",
        {"avatar": avatar, "section": "voices"},
    )


# ---------------------------------------------------------------------------
# Placement question bank — CRUD inside the Control Center.
# Replaces the /django-admin/ route so academic admins manage the bank
# without leaving the platform_admin shell.
# ---------------------------------------------------------------------------

_PQ_SORT_KEYS = {
    "code": "code", "-code": "-code",
    "type": "question_type", "-type": "-question_type",
    "skill": "skill", "-skill": "-skill",
    "level": "cefr_min_level", "-level": "-cefr_min_level",
    "difficulty": "difficulty_score", "-difficulty": "-difficulty_score",
    "updated": "updated_at", "-updated": "-updated_at",
}
_PQ_SORT_DEFAULT = "code"


@control_permission_required(perms.CAP_SETTINGS_MANAGE)
def placement_questions(request):
    """List + filter the placement question bank."""
    from placement.models import PlacementQuestion
    qs = PlacementQuestion.objects.all()

    q = (request.GET.get("q") or "").strip()
    qtype = (request.GET.get("type") or "").strip()
    skill = (request.GET.get("skill") or "").strip()
    active = (request.GET.get("active") or "").strip()
    if q:
        qs = qs.filter(
            Q(code__icontains=q)
            | Q(question_text__icontains=q)
            | Q(question_text_ar__icontains=q)
        )
    if qtype:
        qs = qs.filter(question_type=qtype)
    if skill:
        qs = qs.filter(skill=skill)
    if active == "yes":
        qs = qs.filter(is_active=True)
    elif active == "no":
        qs = qs.filter(is_active=False)

    sort_param = (request.GET.get("sort") or _PQ_SORT_DEFAULT).strip()
    ordering = _PQ_SORT_KEYS.get(sort_param) or _PQ_SORT_KEYS[_PQ_SORT_DEFAULT]
    if sort_param not in _PQ_SORT_KEYS:
        sort_param = _PQ_SORT_DEFAULT
    qs = qs.order_by(ordering, "id")

    written_count = PlacementQuestion.objects.filter(question_type="written", is_active=True).count()
    speaking_count = PlacementQuestion.objects.filter(question_type="speaking", is_active=True).count()

    return _render(request, "platform_admin/placement/questions_list.html", {
        "page_obj": _paginate(request, qs),
        "filters": request.GET,
        "sort_param": sort_param,
        "written_count": written_count,
        "speaking_count": speaking_count,
        "section": "placement_questions",
    })


@control_permission_required(perms.CAP_SETTINGS_MANAGE)
def placement_question_create(request):
    if request.method == "POST":
        form = PlacementQuestionForm(request.POST)
        if form.is_valid():
            obj = form.save()
            from platform_admin.services.audit_log_service import log_action
            log_action(
                request,
                action_type="placement_question.create",
                object_type="PlacementQuestion",
                object_id=obj.pk,
                description=f"Created placement question '{obj.code}'",
            )
            messages.success(request, f"Question '{obj.code}' created.")
            return redirect("platform_admin:placement_questions")
    else:
        form = PlacementQuestionForm()
    return _render(request, "platform_admin/placement/question_form.html", {
        "form": form, "question": None, "section": "placement_questions",
    })


@control_permission_required(perms.CAP_SETTINGS_MANAGE)
def placement_question_edit(request, pk):
    from placement.models import PlacementQuestion
    question = get_object_or_404(PlacementQuestion, pk=pk)
    if request.method == "POST":
        form = PlacementQuestionForm(request.POST, instance=question)
        if form.is_valid():
            obj = form.save()
            from platform_admin.services.audit_log_service import log_action
            log_action(
                request,
                action_type="placement_question.update",
                object_type="PlacementQuestion",
                object_id=obj.pk,
                description=f"Updated placement question '{obj.code}'",
            )
            messages.success(request, f"Question '{obj.code}' saved.")
            return redirect("platform_admin:placement_questions")
    else:
        form = PlacementQuestionForm(instance=question)
    return _render(request, "platform_admin/placement/question_form.html", {
        "form": form, "question": question, "section": "placement_questions",
    })


@require_POST
@control_permission_required(perms.CAP_SETTINGS_MANAGE)
def placement_question_action(request, pk, action):
    """POST-only: toggle-active or delete a placement question."""
    from placement.models import PlacementQuestion
    from platform_admin.services.audit_log_service import log_action
    question = get_object_or_404(PlacementQuestion, pk=pk)
    if action == "toggle":
        question.is_active = not question.is_active
        question.save(update_fields=["is_active", "updated_at"])
        log_action(
            request,
            action_type="placement_question.toggle",
            object_type="PlacementQuestion",
            object_id=question.pk,
            description=f"{'Activated' if question.is_active else 'Deactivated'} '{question.code}'",
        )
        messages.success(
            request,
            f"Question '{question.code}' {'activated' if question.is_active else 'deactivated'}.",
        )
    elif action == "delete":
        # PROTECT on PlacementAttemptQuestion.question — a question
        # already used in an attempt can't be hard-deleted. Deactivate
        # instead so it drops out of future selections.
        from django.db.models import ProtectedError
        code = question.code
        try:
            question.delete()
            log_action(
                request,
                action_type="placement_question.delete",
                object_type="PlacementQuestion",
                object_id=pk,
                description=f"Deleted placement question '{code}'",
            )
            messages.success(request, f"Question '{code}' deleted.")
        except ProtectedError:
            question.is_active = False
            question.save(update_fields=["is_active", "updated_at"])
            messages.warning(
                request,
                f"'{code}' is used in past attempts — deactivated instead of deleted.",
            )
    else:
        raise Http404("Unknown action")
    return redirect("platform_admin:placement_questions")


# ---------------------------------------------------------------------------
# Payment method accounts — bank/wallet details students transfer to.
# Moved into the Control Center so finance admins manage them without
# leaving for Django admin.
# ---------------------------------------------------------------------------

@control_permission_required(perms.CAP_PLANS_VIEW)
def payment_methods(request):
    from payments.models import PaymentMethodAccount
    accounts = PaymentMethodAccount.objects.all().order_by("sort_order", "method")
    return _render(request, "platform_admin/payment_methods/list.html", {
        "accounts": accounts, "section": "payment_methods",
    })


@control_permission_required(perms.CAP_PLANS_MANAGE)
def payment_method_create(request):
    from platform_admin.services.audit_log_service import log_action
    if request.method == "POST":
        form = PaymentMethodAccountForm(request.POST)
        if form.is_valid():
            obj = form.save()
            log_action(
                request, action_type="payment_method.create",
                object_type="PaymentMethodAccount", object_id=obj.pk,
                description=f"Created payment method '{obj.label}'",
            )
            messages.success(request, f"Payment method '{obj.label}' created.")
            return redirect("platform_admin:payment_methods")
    else:
        form = PaymentMethodAccountForm()
    return _render(request, "platform_admin/payment_methods/form.html", {
        "form": form, "account": None, "section": "payment_methods",
    })


@control_permission_required(perms.CAP_PLANS_MANAGE)
def payment_method_edit(request, pk):
    from payments.models import PaymentMethodAccount
    from platform_admin.services.audit_log_service import log_action
    account = get_object_or_404(PaymentMethodAccount, pk=pk)
    if request.method == "POST":
        form = PaymentMethodAccountForm(request.POST, instance=account)
        if form.is_valid():
            obj = form.save()
            log_action(
                request, action_type="payment_method.update",
                object_type="PaymentMethodAccount", object_id=obj.pk,
                description=f"Updated payment method '{obj.label}'",
            )
            messages.success(request, f"Payment method '{obj.label}' saved.")
            return redirect("platform_admin:payment_methods")
    else:
        form = PaymentMethodAccountForm(instance=account)
    return _render(request, "platform_admin/payment_methods/form.html", {
        "form": form, "account": account, "section": "payment_methods",
    })


@require_POST
@control_permission_required(perms.CAP_PLANS_MANAGE)
def payment_method_action(request, pk, action):
    """POST-only: toggle-active or delete a payment method account."""
    from payments.models import PaymentMethodAccount
    from platform_admin.services.audit_log_service import log_action
    account = get_object_or_404(PaymentMethodAccount, pk=pk)
    if action == "toggle":
        account.is_active = not account.is_active
        account.save(update_fields=["is_active", "updated_at"])
        log_action(
            request, action_type="payment_method.toggle",
            object_type="PaymentMethodAccount", object_id=account.pk,
            description=f"{'Activated' if account.is_active else 'Deactivated'} '{account.label}'",
        )
        messages.success(request, f"Payment method '{account.label}' updated.")
    elif action == "delete":
        label = account.label
        account.delete()
        log_action(
            request, action_type="payment_method.delete",
            object_type="PaymentMethodAccount", object_id=pk,
            description=f"Deleted payment method '{label}'",
        )
        messages.success(request, f"Payment method '{label}' deleted.")
    else:
        raise Http404("Unknown action")
    return redirect("platform_admin:payment_methods")
