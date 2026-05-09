from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from accounts.models import Profile
from payments.models import PaymentSubmission


def compute_metrics(now=None):
    now = now or timezone.now()
    today = now.date()
    start_week = now - timedelta(days=7)
    start_month = now - timedelta(days=30)

    total_users = Profile.objects.count()
    new_today = Profile.objects.filter(created_at__date=today).count()
    new_week = Profile.objects.filter(created_at__gte=start_week).count()
    new_month = Profile.objects.filter(created_at__gte=start_month).count()

    start_30 = (now - timedelta(days=29)).date()
    raw = (
        Profile.objects.filter(created_at__date__gte=start_30)
        .annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(c=Count("id"))
        .order_by("d")
    )
    by_date = {r["d"]: r["c"] for r in raw}
    signups_30d = []
    for i in range(30):
        d = start_30 + timedelta(days=i)
        signups_30d.append({"date": d.isoformat(), "count": int(by_date.get(d, 0))})

    placement_done = Profile.objects.filter(placement_completed=True).count()
    activation_rate = (placement_done / total_users * 100) if total_users else 0
    cefr_dist = list(
        Profile.objects.filter(placement_completed=True, cefr_level__isnull=False)
        .values("cefr_level")
        .annotate(c=Count("id"))
        .order_by("cefr_level")
    )

    User = get_user_model()
    dau = User.objects.filter(last_login__date=today).count()
    wau = User.objects.filter(last_login__gte=now - timedelta(days=7)).count()
    mau = User.objects.filter(last_login__gte=now - timedelta(days=30)).count()
    returning = User.objects.filter(last_login__isnull=False, date_joined__lte=now - timedelta(days=1)).count()

    active_subs = Profile.objects.filter(subscription_status="active").count()

    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    revenue_month = (
        PaymentSubmission.objects.filter(status="approved", reviewed_at__gte=start_of_month)
        .aggregate(s=Sum("amount_sdg"))["s"]
        or 0
    )
    revenue_all = (
        PaymentSubmission.objects.filter(status="approved")
        .aggregate(s=Sum("amount_sdg"))["s"]
        or 0
    )
    pending_qs = PaymentSubmission.objects.filter(status="pending")
    pending_count = pending_qs.count()
    pending_total = pending_qs.aggregate(s=Sum("amount_sdg"))["s"] or 0

    reviewed = PaymentSubmission.objects.filter(reviewed_at__isnull=False)
    reviewed_count = reviewed.count()
    approved_count = reviewed.filter(status="approved").count()
    approval_rate = (approved_count / reviewed_count * 100) if reviewed_count else 0

    top_plans = list(
        PaymentSubmission.objects.filter(status="approved")
        .values("plan")
        .annotate(c=Count("id"))
        .order_by("-c")
    )
    top_methods = list(
        PaymentSubmission.objects.filter(status="approved")
        .values("method")
        .annotate(c=Count("id"))
        .order_by("-c")
    )

    recent_payments = PaymentSubmission.objects.all()[:10]

    return {
        "now": now,
        "acquisition": {
            "total_users": total_users,
            "new_today": new_today,
            "new_week": new_week,
            "new_month": new_month,
            "signups_30d": signups_30d,
        },
        "activation": {
            "placement_done": placement_done,
            "activation_rate": activation_rate,
            "cefr_dist": cefr_dist,
        },
        "retention": {
            "dau": dau,
            "wau": wau,
            "mau": mau,
            "returning": returning,
        },
        "revenue": {
            "active_subs": active_subs,
            "revenue_month": revenue_month,
            "revenue_all": revenue_all,
            "pending_count": pending_count,
            "pending_total": pending_total,
            "approval_rate": approval_rate,
            "top_plans": top_plans,
            "top_methods": top_methods,
        },
        "recent_payments": recent_payments,
    }
