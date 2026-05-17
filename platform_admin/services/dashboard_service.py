from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from accounts.models import Profile
from courses.models import Course
from payments.models import PaymentSubmission
from platform_admin.models import PlatformStudentFlag
from platform_admin.permissions import courses_for_user, has_capability, CAP_PAYMENTS_VIEW


def dashboard_metrics_for(user) -> dict:
    now = timezone.now()
    today = now.date()
    week_start = now - timedelta(days=7)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    User = get_user_model()

    student_profiles = Profile.objects.select_related("user").filter(role="student")
    courses = courses_for_user(user, Course.objects.all())
    payments = PaymentSubmission.objects.all()

    revenue_this_month = 0
    pending_payments = 0
    if has_capability(user, CAP_PAYMENTS_VIEW):
        revenue_this_month = (
            payments.filter(status="approved", reviewed_at__gte=month_start).aggregate(total=Sum("amount_sdg"))["total"]
            or 0
        )
        pending_payments = payments.filter(status__in=["pending", "needs_review"]).count()

    daily_plans_completed = 0
    try:
        from daily_learning.models import DailyLearningPlan
        daily_plans_completed = DailyLearningPlan.objects.filter(date=today, status="completed").count()
    except Exception:
        daily_plans_completed = 0

    ai_usage_today = 0
    ai_failures_today = 0
    try:
        from ai_engine.models import ModelPredictionLog
        ai_qs = ModelPredictionLog.objects.filter(created_at__date=today)
        ai_usage_today = ai_qs.count()
        ai_failures_today = ai_qs.filter(success=False).count()
    except Exception:
        pass

    avg_level = student_profiles.exclude(cefr_level__isnull=True).exclude(cefr_level="").values("cefr_level").annotate(c=Count("id")).order_by("-c").first()

    top_weaknesses = []
    try:
        from learning_core.models import UserWeakness
        top_weaknesses = list(
            UserWeakness.objects.filter(status="active")
            .values("skill__name", "grammar_topic__name")
            .annotate(count=Count("id"), avg_priority=Avg("priority_score"))
            .order_by("-count", "-avg_priority")[:5]
        )
    except Exception:
        top_weaknesses = []

    cards = [
        {"label": "Total Students", "label_ar": "إجمالي الطلاب", "value": student_profiles.count(), "icon": "users"},
        {"label": "Active Today", "label_ar": "نشطون اليوم", "value": User.objects.filter(last_login__date=today).count(), "icon": "activity"},
        {"label": "Pending Payments", "label_ar": "مدفوعات قيد المراجعة", "value": pending_payments, "icon": "clock"},
        {"label": "Pending Course Reviews", "label_ar": "كورسات تنتظر المراجعة", "value": courses.filter(status="pending_review").count(), "icon": "file-search"},
        {"label": "AI Usage Today", "label_ar": "استخدام AI اليوم", "value": ai_usage_today, "icon": "bot"},
        {"label": "At-risk Students", "label_ar": "طلاب معرضون للتوقف", "value": PlatformStudentFlag.objects.exclude(risk_status="normal").count(), "icon": "alert-triangle"},
        {"label": "Daily Plans Completed", "label_ar": "خطط اليوم المكتملة", "value": daily_plans_completed, "icon": "check-circle"},
        {"label": "Revenue This Month", "label_ar": "إيراد هذا الشهر", "value": f"{revenue_this_month:,} SDG", "icon": "wallet"},
    ]

    return {
        "now": now,
        "cards": cards,
        "student_summary": {
            "new_week": student_profiles.filter(created_at__gte=week_start).count(),
            "paid": student_profiles.filter(subscription_status="active").count(),
            "expired": student_profiles.filter(subscription_status="expired").count(),
            "average_level": avg_level["cefr_level"] if avg_level else "-",
        },
        "course_summary": {
            "published": courses.filter(status="published").count(),
            "pending_review": courses.filter(status="pending_review").count(),
            "draft": courses.filter(status="draft").count(),
        },
        "ai_summary": {
            "usage_today": ai_usage_today,
            "failures_today": ai_failures_today,
        },
        "top_weaknesses": top_weaknesses,
        "recent_payments": payments.select_related("user").order_by("-created_at")[:8] if has_capability(user, CAP_PAYMENTS_VIEW) else [],
        "recent_students": student_profiles.order_by("-created_at")[:8],
    }
