"""Custom admin dashboard pages for AI usage & cost control.

Rendered inside the platform_admin control-center shell and gated by
``control_login_required`` (admin/control users only — cost is admin-visible).
"""
from __future__ import annotations

import csv
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from platform_admin.decorators import control_login_required

from . import constants as C
from .models import AIUsageLog, StudentDailyAILimit
from .services import limit_service
from .services.cost_calculator import safe_decimal


def _parse_date(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


def _cost(qs) -> Decimal:
    return safe_decimal(qs.aggregate(c=Sum("estimated_cost_usd"))["c"] or 0)


def _pct(part: Decimal, whole) -> int:
    whole = safe_decimal(whole)
    if whole <= 0:
        return 0
    return int(min(Decimal("100"), (part / whole) * Decimal("100")))


@control_login_required
def overview(request):
    today = timezone.localdate()
    yesterday = today - timedelta(days=1)
    month_start = today.replace(day=1)
    logs = AIUsageLog.objects

    today_qs = logs.filter(usage_date=today)
    today_spend = _cost(today_qs)
    month_spend = _cost(logs.filter(usage_date__gte=month_start))

    daily_budget = safe_decimal(getattr(settings, "AI_USAGE_DAILY_BUDGET_USD", "0"))
    monthly_budget = safe_decimal(getattr(settings, "AI_USAGE_MONTHLY_BUDGET_USD", "0"))

    top_users = list(
        today_qs.filter(user__isnull=False).values("user__username")
        .annotate(cost=Sum("estimated_cost_usd")).order_by("-cost")[:10]
    )
    top_features = list(
        today_qs.values("feature").annotate(cost=Sum("estimated_cost_usd"),
                                            requests=Count("id")).order_by("-cost")[:10]
    )
    top_models = list(
        today_qs.values("model_name").annotate(cost=Sum("estimated_cost_usd")).order_by("-cost")[:10]
    )
    tutor_minutes = today_qs.filter(feature=C.FEATURE_AI_TUTOR).aggregate(
        m=Sum("ai_minutes_used"))["m"] or Decimal("0")

    ctx = {
        "lang": getattr(request, "LANGUAGE_CODE", "en"),
        "today": today,
        "today_spend": today_spend,
        "yesterday_spend": _cost(logs.filter(usage_date=yesterday)),
        "month_spend": month_spend,
        "requests_today": today_qs.count(),
        "tokens_today": today_qs.aggregate(t=Sum("total_tokens"))["t"] or 0,
        "tutor_minutes_today": tutor_minutes,
        "failed_today": today_qs.filter(status=C.STATUS_FAILED).count(),
        "top_users": top_users,
        "top_features": top_features,
        "top_models": top_models,
        "daily_budget": daily_budget,
        "monthly_budget": monthly_budget,
        "daily_budget_pct": _pct(today_spend, daily_budget),
        "monthly_budget_pct": _pct(month_spend, monthly_budget),
    }
    return render(request, "ai_usage/overview.html", ctx)


@control_login_required
def daily_report(request):
    today = timezone.localdate()
    date_from = _parse_date(request.GET.get("date_from"), today - timedelta(days=7))
    date_to = _parse_date(request.GET.get("date_to"), today)
    qs = AIUsageLog.objects.filter(usage_date__gte=date_from, usage_date__lte=date_to)
    for field in ("feature", "role", "model_name", "status", "organization"):
        val = request.GET.get(field)
        if val:
            qs = qs.filter(**{field: val})
    uid = request.GET.get("user")
    if uid:
        qs = qs.filter(user_id=uid)
    rows = qs.select_related("user").order_by("-created_at")[:500]
    ctx = {
        "lang": getattr(request, "LANGUAGE_CODE", "en"),
        "rows": rows, "date_from": date_from, "date_to": date_to,
        "feature_choices": C.FEATURE_CHOICES, "role_choices": C.ROLE_CHOICES,
        "status_choices": C.STATUS_CHOICES,
        "filters": request.GET,
    }
    return render(request, "ai_usage/daily_report.html", ctx)


@control_login_required
def student_usage(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)
    username = request.GET.get("q", "").strip()
    student = None
    data = None
    if username:
        from django.contrib.auth import get_user_model
        student = get_user_model().objects.filter(username=username).first()
    if student is not None:
        limit_row = limit_service.get_student_daily_limit(student)
        logs = AIUsageLog.objects.filter(user=student)
        last_tutor = logs.filter(feature=C.FEATURE_AI_TUTOR).order_by("-created_at").first()
        data = {
            "limit": limit_row,
            "month_cost": _cost(logs.filter(usage_date__gte=month_start)),
            "month_requests": logs.filter(usage_date__gte=month_start).count(),
            "last_tutor": last_tutor,
            "abnormal": _cost(logs.filter(usage_date=today)) > safe_decimal(
                getattr(settings, "AI_USAGE_USER_DAILY_ALERT_USD", "0")),
        }
    ctx = {
        "lang": getattr(request, "LANGUAGE_CODE", "en"),
        "student": student, "data": data, "q": username,
    }
    return render(request, "ai_usage/student_usage.html", ctx)


@control_login_required
def export_csv(request):
    today = timezone.localdate()
    date_from = _parse_date(request.GET.get("date_from"), today - timedelta(days=7))
    date_to = _parse_date(request.GET.get("date_to"), today)
    qs = AIUsageLog.objects.filter(
        usage_date__gte=date_from, usage_date__lte=date_to
    ).select_related("user").order_by("usage_date")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="ai_usage_{date_from}_{date_to}.csv"'
    )
    writer = csv.writer(response)
    writer.writerow([
        "date", "user", "role", "feature", "model", "requests_tokens_in",
        "tokens_out", "total_tokens", "audio_in_s", "audio_out_s",
        "ai_minutes_used", "estimated_cost_usd", "status", "latency_ms",
    ])
    for r in qs.iterator():
        writer.writerow([
            r.usage_date, getattr(r.user, "username", ""), r.role, r.feature,
            r.model_name, r.input_tokens, r.output_tokens, r.total_tokens,
            r.audio_input_seconds, r.audio_output_seconds, r.ai_minutes_used,
            r.estimated_cost_usd, r.status, r.latency_ms or "",
        ])
    return response
    # TODO: Excel (.xlsx) and PDF exports — add openpyxl / reportlab renderers
    # once those deps are approved. CSV is the supported format for now.
