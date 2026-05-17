from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from accounts.models import Profile
from courses.models import Course, CourseEnrollment
from platform_admin.models import PlatformStudentFlag, PlatformStudentNote
from platform_admin.permissions import students_for_user
from platform_admin.services.audit_log_service import log_action


def student_queryset_for(user, params=None):
    User = get_user_model()
    qs = User.objects.select_related("profile", "platform_flag").filter(profile__role="student")
    qs = students_for_user(user, qs)
    params = params or {}

    q = (params.get("q") or params.get("search") or "").strip()
    if q:
        qs = qs.filter(
            Q(username__icontains=q)
            | Q(email__icontains=q)
            | Q(profile__full_name__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
        )

    level = (params.get("level") or "").strip()
    if level:
        qs = qs.filter(profile__cefr_level=level)

    subscription = (params.get("subscription") or "").strip()
    if subscription:
        qs = qs.filter(profile__subscription_status=subscription)

    language = (params.get("language") or "").strip()
    if language:
        qs = qs.filter(profile__preferred_language=language)

    onboarding_path = (params.get("onboarding_path") or "").strip()
    if onboarding_path:
        qs = qs.filter(profile__onboarding_path=onboarding_path)

    active = (params.get("active") or "").strip()
    if active == "yes":
        qs = qs.filter(last_login__gte=timezone.now() - timedelta(days=14))
    elif active == "no":
        qs = qs.filter(Q(last_login__isnull=True) | Q(last_login__lt=timezone.now() - timedelta(days=14)))

    risk = (params.get("risk") or "").strip()
    if risk:
        if risk == "normal":
            qs = qs.filter(Q(platform_flag__risk_status="normal") | Q(platform_flag__isnull=True))
        else:
            qs = qs.filter(platform_flag__risk_status=risk)

    return qs.order_by("-date_joined").distinct()


def student_row(student) -> dict:
    profile = getattr(student, "profile", None)
    flag = getattr(student, "platform_flag", None)
    xp_total = 0
    streak = 0
    try:
        xp_total = getattr(student.xp, "total_xp", 0)
    except Exception:
        xp_total = 0
    try:
        from motivation.services import streak_service
        streak = streak_service.get_current_streak(student)
    except Exception:
        streak = 0
    return {
        "user": student,
        "name": (getattr(profile, "full_name", "") or student.get_full_name() or student.email or student.username),
        "email": student.email,
        "language": getattr(profile, "preferred_language", "-"),
        "level": getattr(profile, "cefr_level", None) or "-",
        "onboarding_path": getattr(profile, "onboarding_path", "") or "-",
        "subscription": getattr(profile, "subscription_status", "-"),
        "last_login": student.last_login,
        "xp": xp_total,
        "streak": streak,
        "risk_status": getattr(flag, "risk_status", "normal"),
    }


def student_detail_context(student) -> dict:
    profile = student.profile
    flag, _ = PlatformStudentFlag.objects.get_or_create(user=student)
    notes = student.platform_notes.select_related("author")[:20]
    enrollments = (
        CourseEnrollment.objects.filter(user=student)
        .select_related("course", "course__level", "course__teacher")
        .order_by("-enrolled_at")
    )

    placement_results = []
    placement_attempts = []
    try:
        placement_results = student.placement_results.all()[:5]
        placement_attempts = student.placement_attempts.all()[:5]
    except Exception:
        pass

    weaknesses = []
    recent_errors = []
    recommendations = []
    try:
        weaknesses = student.weaknesses.select_related("skill", "grammar_topic").order_by("-priority_score")[:10]
        recent_errors = student.user_errors.select_related("skill", "grammar_topic").order_by("-created_at")[:10]
        recommendations = student.learning_recommendations.order_by("-priority")[:10]
    except Exception:
        pass

    tutor_conversations = []
    tutor_messages = []
    try:
        tutor_conversations = student.tutor_conversations.order_by("-updated_at")[:8]
        tutor_messages = []
        for conversation in tutor_conversations[:3]:
            tutor_messages.extend(list(conversation.messages.order_by("-created_at")[:3]))
    except Exception:
        pass

    payments = student.payment_submissions.order_by("-created_at")[:10]

    motivation = {"xp_total": 0, "badges": [], "achievements": [], "streak": 0}
    try:
        motivation["xp_total"] = getattr(student.xp, "total_xp", 0)
        motivation["badges"] = student.badges_earned.all()[:10]
        motivation["achievements"] = student.achievements_earned.select_related("achievement")[:10]
        from motivation.services import streak_service
        motivation["streak"] = streak_service.get_current_streak(student)
    except Exception:
        pass

    today_plan = None
    try:
        from daily_learning.models import DailyLearningPlan
        today_plan = DailyLearningPlan.objects.filter(user=student, date=timezone.localdate()).prefetch_related("items").first()
    except Exception:
        pass

    return {
        "student": student,
        "profile": profile,
        "flag": flag,
        "notes": notes,
        "enrollments": enrollments,
        "placement_results": placement_results,
        "placement_attempts": placement_attempts,
        "weaknesses": weaknesses,
        "recent_errors": recent_errors,
        "recommendations": recommendations,
        "tutor_conversations": tutor_conversations,
        "tutor_messages": tutor_messages,
        "payments": payments,
        "motivation": motivation,
        "today_plan": today_plan,
    }


def reset_placement(request, student):
    profile = student.profile
    profile.placement_completed = False
    profile.onboarding_completed = False
    profile.onboarding_path = ""
    profile.initial_cefr_level = None
    profile.onboarding_completed_at = None
    profile.save(update_fields=[
        "placement_completed",
        "onboarding_completed",
        "onboarding_path",
        "initial_cefr_level",
        "onboarding_completed_at",
    ])
    log_action(
        request,
        action_type="student.reset_placement",
        target_user=student,
        object_type="auth.User",
        object_id=student.pk,
        description=f"Reset placement for {student.email or student.username}",
    )


def mark_risk(request, student, risk_status: str):
    flag, _ = PlatformStudentFlag.objects.get_or_create(user=student)
    old_status = flag.risk_status
    flag.risk_status = risk_status
    flag.save(update_fields=["risk_status", "updated_at"])
    log_action(
        request,
        action_type="student.mark_risk",
        target_user=student,
        object_type="PlatformStudentFlag",
        object_id=flag.pk,
        description=f"Changed student risk from {old_status} to {risk_status}",
        metadata={"old_status": old_status, "new_status": risk_status},
    )


def deactivate_student(request, student):
    student.is_active = False
    student.save(update_fields=["is_active"])
    flag, _ = PlatformStudentFlag.objects.get_or_create(user=student)
    flag.is_deactivated_by_admin = True
    flag.save(update_fields=["is_deactivated_by_admin", "updated_at"])
    log_action(
        request,
        action_type="student.deactivate",
        target_user=student,
        object_type="auth.User",
        object_id=student.pk,
        description=f"Deactivated student {student.email or student.username}",
    )


def add_note(request, student, note: str, is_private: bool = False) -> PlatformStudentNote:
    obj = PlatformStudentNote.objects.create(
        student=student,
        author=request.user,
        note=note,
        is_private=is_private,
    )
    log_action(
        request,
        action_type="student.add_note",
        target_user=student,
        object_type="PlatformStudentNote",
        object_id=obj.pk,
        description="Added student note",
        metadata={"private": is_private},
    )
    return obj


def assign_course(request, student, course: Course):
    enrollment, created = CourseEnrollment.objects.get_or_create(user=student, course=course)
    if not created and enrollment.status != "active":
        enrollment.status = "active"
        enrollment.save(update_fields=["status"])
    log_action(
        request,
        action_type="student.assign_course",
        target_user=student,
        object_type="Course",
        object_id=course.pk,
        description=f"Assigned course '{course.title}' to {student.email or student.username}",
        metadata={"created": created},
    )
    return enrollment


def send_notification(request, student, title: str, message: str):
    try:
        from notifications import constants as C
        from notifications.services import NotificationService

        NotificationService().trigger(
            getattr(C, "MOTIVATION_MESSAGE", "motivation_message"),
            user=student,
            actor=request.user,
            payload={"title": title, "message": message, "dedup_key": f"manual:{student.pk}:{timezone.now().timestamp()}"},
        )
    except Exception:
        pass
    log_action(
        request,
        action_type="student.send_notification",
        target_user=student,
        object_type="auth.User",
        object_id=student.pk,
        description=f"Sent manual notification to {student.email or student.username}",
        metadata={"title": title},
    )
