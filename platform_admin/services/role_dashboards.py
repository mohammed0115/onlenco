"""Per-role admin dashboards.

Each function returns a context dict tailored to one role. Heavy/optional
imports are wrapped in try/except so installed-app drift never breaks a
dashboard render.
"""
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from courses.models import Course, Lesson
from payments.models import PaymentSubmission

from .. import permissions as perms
from ..models import PlatformAuditLog, PlatformStudentFlag, PlatformStudentNote


User = get_user_model()


def _safe_count(qs) -> int:
    try:
        return qs.count()
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Academic Admin — content review & teacher activity
# ---------------------------------------------------------------------------

def academic_dashboard_context() -> dict:
    pending_courses = Course.objects.filter(status="pending_review")
    pending_lessons = Lesson.objects.filter(status="pending_review")
    published_courses = Course.objects.filter(status="published")
    teachers = User.objects.filter(groups__name=perms.GROUP_TEACHER)

    cefr_rows = []
    try:
        from accounts.models import Profile
        cefr_rows = list(
            Profile.objects.exclude(cefr_level="")
            .values("cefr_level")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )
    except Exception:
        pass

    top_weaknesses = []
    try:
        from learning_core.models import UserWeakness
        top_weaknesses = list(
            UserWeakness.objects.values("skill__name", "grammar_topic__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:8]
        )
    except Exception:
        pass

    return {
        "cards": [
            {"key": "pending_courses", "value": pending_courses.count(),
             "label_en": "Courses awaiting review", "label_ar": "كورسات تنتظر مراجعة", "icon": "book-open-check"},
            {"key": "pending_lessons", "value": pending_lessons.count(),
             "label_en": "Lessons awaiting review", "label_ar": "دروس تنتظر مراجعة", "icon": "file-clock"},
            {"key": "published_courses", "value": published_courses.count(),
             "label_en": "Published courses", "label_ar": "كورسات منشورة", "icon": "book-marked"},
            {"key": "active_teachers", "value": teachers.filter(is_active=True).count(),
             "label_en": "Active teachers", "label_ar": "معلمون نشطون", "icon": "graduation-cap"},
        ],
        "pending_courses": pending_courses.select_related("teacher", "level").order_by("-updated_at")[:8],
        "pending_lessons": pending_lessons.select_related("course").order_by("-updated_at")[:8],
        "cefr_rows": cefr_rows,
        "top_weaknesses": top_weaknesses,
    }


# ---------------------------------------------------------------------------
# Finance Admin — payments & subscriptions
# ---------------------------------------------------------------------------

def finance_dashboard_context() -> dict:
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    pending = PaymentSubmission.objects.filter(status="pending")
    approved_month = PaymentSubmission.objects.filter(status="approved", reviewed_at__gte=month_start)
    revenue_month = approved_month.aggregate(total=Sum("amount_sdg"))["total"] or 0

    expiring_soon = 0
    expired = 0
    try:
        from accounts.models import Profile
        window = now + timedelta(days=7)
        expiring_soon = Profile.objects.filter(
            subscription_status="active",
            subscription_expires_at__gt=now,
            subscription_expires_at__lte=window,
        ).count()
        expired = Profile.objects.filter(subscription_status="expired").count()
    except Exception:
        pass

    plan_rows = list(
        PaymentSubmission.objects.filter(status="approved")
        .values("plan")
        .annotate(count=Count("id"), revenue=Sum("amount_sdg"))
        .order_by("-revenue")[:6]
    )

    return {
        "cards": [
            {"key": "pending_payments", "value": pending.count(),
             "label_en": "Payments to review", "label_ar": "دفعات قيد المراجعة", "icon": "wallet"},
            {"key": "revenue_month", "value": f"{revenue_month:,} SDG",
             "label_en": "Revenue this month", "label_ar": "إيرادات الشهر", "icon": "trending-up"},
            {"key": "expiring_soon", "value": expiring_soon,
             "label_en": "Expiring in 7 days", "label_ar": "تنتهي خلال 7 أيام", "icon": "alarm-clock"},
            {"key": "expired", "value": expired,
             "label_en": "Expired subscriptions", "label_ar": "اشتراكات منتهية", "icon": "circle-off"},
        ],
        "recent_pending": pending.select_related("user").order_by("-submitted_at")[:10],
        "recent_approved": approved_month.select_related("user").order_by("-reviewed_at")[:10],
        "plan_rows": plan_rows,
    }


# ---------------------------------------------------------------------------
# Support Admin — student care
# ---------------------------------------------------------------------------

def support_dashboard_context() -> dict:
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    at_risk = PlatformStudentFlag.objects.filter(risk_status__in=["at_risk", "critical"])
    inactive = User.objects.filter(last_login__lt=week_ago, is_active=True)
    recent_notes = PlatformStudentNote.objects.select_related("student", "author").order_by("-created_at")[:10]

    new_signups = User.objects.filter(date_joined__gte=week_ago).count()

    notification_count = 0
    try:
        from notifications.models import NotificationEvent
        notification_count = NotificationEvent.objects.filter(created_at__gte=week_ago).count()
    except Exception:
        pass

    return {
        "cards": [
            {"key": "at_risk", "value": at_risk.count(),
             "label_en": "Students at risk", "label_ar": "طلاب في خطر", "icon": "alert-triangle"},
            {"key": "inactive_week", "value": inactive.count(),
             "label_en": "Inactive 7+ days", "label_ar": "غير نشط 7+ أيام", "icon": "user-x"},
            {"key": "new_signups", "value": new_signups,
             "label_en": "New signups this week", "label_ar": "تسجيلات جديدة هذا الأسبوع", "icon": "user-plus"},
            {"key": "notifications_week", "value": notification_count,
             "label_en": "Notifications sent (7d)", "label_ar": "إشعارات مرسلة (7 أيام)", "icon": "bell"},
        ],
        "at_risk_students": at_risk.select_related("user").order_by("-updated_at")[:10],
        "recent_notes": recent_notes,
        "inactive_sample": inactive.order_by("-date_joined")[:10],
    }


# ---------------------------------------------------------------------------
# AI Admin — model monitoring & dataset review
# ---------------------------------------------------------------------------

def ai_dashboard_context() -> dict:
    today = timezone.localdate()
    requests_today = 0
    fallback_rate = 0.0
    avg_latency_ms = 0
    failed_requests = 0
    pending_examples = 0
    recent_evals = []
    pending_examples_qs = None

    try:
        from ai_engine.models import ModelPredictionLog
        logs_today = ModelPredictionLog.objects.filter(created_at__date=today)
        requests_today = logs_today.count()
        if requests_today:
            fallback_rate = round(
                logs_today.filter(provider__icontains="openai").count() * 100 / requests_today, 1
            )
        avg_latency_ms = int(logs_today.aggregate(avg=Avg("latency_ms"))["avg"] or 0)
        failed_requests = logs_today.filter(success=False).count()
    except Exception:
        pass

    try:
        from ai_training.models import AITrainingExample
        pending_examples_qs = AITrainingExample.objects.filter(is_approved__isnull=True)
        pending_examples = pending_examples_qs.count()
    except Exception:
        pass

    try:
        from ai_training.models import EvaluationRun
        recent_evals = list(EvaluationRun.objects.order_by("-created_at")[:8])
    except Exception:
        pass

    cost_estimate = 0
    try:
        from ai_engine.models import ModelPredictionLog
        cost_estimate = ModelPredictionLog.objects.filter(
            created_at__date=today
        ).aggregate(total=Sum("cost_usd"))["total"] or 0
    except Exception:
        pass

    return {
        "cards": [
            {"key": "requests_today", "value": requests_today,
             "label_en": "AI requests today", "label_ar": "طلبات AI اليوم", "icon": "activity"},
            {"key": "fallback_rate", "value": f"{fallback_rate}%",
             "label_en": "OpenAI fallback rate", "label_ar": "نسبة الرجوع لـ OpenAI", "icon": "git-branch"},
            {"key": "avg_latency", "value": f"{avg_latency_ms} ms",
             "label_en": "Avg latency", "label_ar": "متوسط الزمن", "icon": "timer"},
            {"key": "pending_examples", "value": pending_examples,
             "label_en": "Training examples pending", "label_ar": "أمثلة تدريب تنتظر", "icon": "database"},
        ],
        "failed_requests": failed_requests,
        "cost_estimate_usd": cost_estimate,
        "pending_examples_sample": list(pending_examples_qs.order_by("-created_at")[:8]) if pending_examples_qs is not None else [],
        "recent_evals": recent_evals,
    }


# ---------------------------------------------------------------------------
# Read-only Admin — derive context from dashboard service, strip actions
# ---------------------------------------------------------------------------

def readonly_dashboard_context(user) -> dict:
    from .dashboard_service import dashboard_metrics_for
    metrics = dashboard_metrics_for(user)
    metrics["readonly_notice"] = True
    return metrics


# ---------------------------------------------------------------------------
# Routing: pick the right dashboard for a user
# ---------------------------------------------------------------------------

# Order matters: most-specific role wins for single-role accounts. Super /
# Platform Admin (and superusers) keep the overview dashboard.
_ROLE_TO_URL = [
    (perms.GROUP_ACADEMIC_ADMIN, "platform_admin:dashboard_academic"),
    (perms.GROUP_FINANCE_ADMIN, "platform_admin:dashboard_finance"),
    (perms.GROUP_SUPPORT_ADMIN, "platform_admin:dashboard_support"),
    (perms.GROUP_AI_ADMIN, "platform_admin:dashboard_ai"),
    (perms.GROUP_READ_ONLY_ADMIN, "platform_admin:dashboard_readonly"),
]


def dashboard_url_for(user) -> str:
    """Return the URL name of the dashboard tailored to this user.

    Super Admin, Platform Admin, superusers, and any account holding two or
    more admin roles get the shared overview at ``platform_admin:dashboard``.
    """
    if getattr(user, "is_superuser", False):
        return "platform_admin:dashboard"
    roles = perms.user_role_names(user)
    if perms.GROUP_SUPER_ADMIN in roles or perms.GROUP_PLATFORM_ADMIN in roles:
        return "platform_admin:dashboard"
    admin_roles = roles - {perms.GROUP_TEACHER}
    if len(admin_roles) > 1:
        return "platform_admin:dashboard"
    for role, url_name in _ROLE_TO_URL:
        if role in roles:
            return url_name
    return "platform_admin:dashboard"
