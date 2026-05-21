from __future__ import annotations

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounts.models import Profile
from courses.models import Course, CourseEnrollment
from payments.models import PaymentSubmission


def learning_analytics() -> dict:
    cefr_distribution = list(
        Profile.objects.exclude(cefr_level__isnull=True)
        .exclude(cefr_level="")
        .values("cefr_level")
        .annotate(count=Count("id"))
        .order_by("cefr_level")
    )
    completion = CourseEnrollment.objects.aggregate(avg=Avg("progress_percentage"))["avg"] or 0
    top_weaknesses = []
    try:
        from learning_core.models import UserWeakness
        top_weaknesses = list(
            UserWeakness.objects.values("skill__name", "grammar_topic__name")
            .annotate(count=Count("id"), avg=Avg("priority_score"))
            .order_by("-count")[:10]
        )
    except Exception:
        pass
    return {
        "cefr_distribution": cefr_distribution,
        "course_completion_average": round(completion, 1),
        "top_weaknesses": top_weaknesses,
    }


def engagement_analytics() -> dict:
    plans = {}
    try:
        from daily_learning.models import DailyLearningPlan
        plans = {
            "completed": DailyLearningPlan.objects.filter(status="completed").count(),
            "total": DailyLearningPlan.objects.count(),
        }
    except Exception:
        plans = {"completed": 0, "total": 0}
    return {"daily_plans": plans}


def _monthly_revenue(qs, months: int = 6) -> list[dict]:
    """Approved-payment revenue for the last ``months`` calendar months,
    oldest first. Empty months are filled in so the chart axis is stable.
    """
    today = timezone.localdate()
    buckets: list[tuple[int, int]] = []
    y, m = today.year, today.month
    for _ in range(months):
        buckets.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    buckets.reverse()

    rows = (
        qs.filter(status="approved", reviewed_at__isnull=False)
        .annotate(month=TruncMonth("reviewed_at"))
        .values("month")
        .annotate(total=Sum("amount_sdg"))
    )
    by_month = {
        (r["month"].year, r["month"].month): int(r["total"] or 0)
        for r in rows if r["month"]
    }
    series = [
        {"label": f"{yy}-{mm:02d}", "total": by_month.get((yy, mm), 0)}
        for (yy, mm) in buckets
    ]
    peak = max((s["total"] for s in series), default=0) or 1
    for s in series:
        s["pct"] = round(s["total"] * 100 / peak)
    return series


def financial_analytics() -> dict:
    qs = PaymentSubmission.objects.all()
    approved = qs.filter(status="approved")
    by_method = list(
        approved.values("method")
        .annotate(total=Sum("amount_sdg"), count=Count("id"))
        .order_by("-total")
    )
    by_plan = list(
        approved.values("plan")
        .annotate(total=Sum("amount_sdg"), count=Count("id"))
        .order_by("-total")
    )
    return {
        "revenue": approved.aggregate(total=Sum("amount_sdg"))["total"] or 0,
        "pending": qs.filter(status__in=["pending", "needs_review"]).count(),
        "approved": approved.count(),
        "refunded": qs.filter(status="refunded").count(),
        "expired_subscriptions": Profile.objects.filter(subscription_status="expired").count(),
        "monthly": _monthly_revenue(qs),
        "by_method": by_method,
        "by_plan": by_plan,
    }


def content_analytics() -> dict:
    return {
        "published_courses": Course.objects.filter(status="published").count(),
        "pending_courses": Course.objects.filter(status="pending_review").count(),
        "archived_courses": Course.objects.filter(status="archived").count(),
        "most_completed": Course.objects.annotate(enrolled=Count("enrollments")).order_by("-enrolled")[:10],
    }


def ai_analytics() -> dict:
    try:
        from ai_engine.models import ModelPredictionLog
        qs = ModelPredictionLog.objects.all()
        total = qs.count()
        return {
            "total": total,
            "openai": qs.filter(provider__icontains="openai").count(),
            "local": qs.filter(provider__icontains="local").count(),
            "fallback": qs.filter(fallback_used=True).count(),
            "errors": qs.filter(success=False).count(),
            "latency": int(qs.aggregate(avg=Avg("latency_ms"))["avg"] or 0),
        }
    except Exception:
        return {"total": 0, "openai": 0, "local": 0, "fallback": 0, "errors": 0, "latency": 0}


def analytics_overview() -> dict:
    return {
        "learning": learning_analytics(),
        "engagement": engagement_analytics(),
        "financial": financial_analytics(),
        "content": content_analytics(),
        "ai": ai_analytics(),
    }
