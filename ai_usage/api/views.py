"""DRF endpoints for AI usage & limits.

Scoping:
* Student  → only their own usage; remaining minutes; cost hidden unless
             ``AI_USAGE_STUDENT_CAN_VIEW_COST``.
* Teacher  → only usage they generated (their own user rows).
* Admin    → everything; cost visible; recalculation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import constants as C
from ..models import AIDailyUsageSummary, AIUsageLog, StudentDailyAILimit
from ..services import aggregation, limit_service, usage_logger
from . import permissions as P
from .serializers import (
    AIUsageLogSerializer,
    StudentDailyAILimitSerializer,
    strip_cost,
)


def _parse_date(value, default):
    if not value:
        return default
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


def _scope_logs(user, qs):
    """Restrict a log queryset to what ``user`` is allowed to see."""
    if P.is_admin(user):
        return qs
    # Student & teacher: only their own rows.
    return qs.filter(user=user)


def _totals(qs, include_cost: bool) -> dict:
    agg = qs.aggregate(
        requests=Count("id"),
        tokens=Sum("total_tokens"),
        minutes=Sum("ai_minutes_used"),
        cost=Sum("estimated_cost_usd"),
        failed=Count("id", filter=Q(status=C.STATUS_FAILED)),
    )
    out = {
        "requests": agg["requests"] or 0,
        "tokens": int(agg["tokens"] or 0),
        "minutes": str(agg["minutes"] or Decimal("0")),
        "failed_requests": agg["failed"] or 0,
    }
    if include_cost:
        out["estimated_cost_usd"] = str(agg["cost"] or Decimal("0"))
    return out


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary_today(request):
    today = timezone.localdate()
    qs = _scope_logs(request.user, AIUsageLog.objects.filter(usage_date=today))
    include_cost = P.is_admin(request.user) or P.student_can_view_cost()
    return Response({"date": str(today), **_totals(qs, include_cost)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def summary_month(request):
    today = timezone.localdate()
    start = today.replace(day=1)
    qs = _scope_logs(request.user, AIUsageLog.objects.filter(usage_date__gte=start))
    include_cost = P.is_admin(request.user) or P.student_can_view_cost()
    return Response({"month_start": str(start), "date": str(today),
                     **_totals(qs, include_cost)})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def daily(request):
    """Per-day log list with filters. Paginated via DRF default page param."""
    today = timezone.localdate()
    date_from = _parse_date(request.query_params.get("date_from"), today - timedelta(days=30))
    date_to = _parse_date(request.query_params.get("date_to"), today)
    qs = AIUsageLog.objects.filter(usage_date__gte=date_from, usage_date__lte=date_to)
    qs = _scope_logs(request.user, qs)

    for field in ("feature", "role", "model_name", "status", "organization"):
        val = request.query_params.get(field)
        if val:
            qs = qs.filter(**{field: val})
    if P.is_admin(request.user):
        uid = request.query_params.get("user")
        if uid:
            qs = qs.filter(user_id=uid)

    qs = qs.order_by("-created_at")
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    page = paginator.paginate_queryset(qs, request)
    data = AIUsageLogSerializer(page, many=True).data
    if not (P.is_admin(request.user) or P.student_can_view_cost()):
        data = strip_cost(data)
    return paginator.get_paginated_response(data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_detail(request, user_id):
    """Per-user usage. Self always allowed; others admin-only."""
    if str(request.user.id) != str(user_id) and not P.is_admin(request.user):
        return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
    today = timezone.localdate()
    start = today.replace(day=1)
    qs = AIUsageLog.objects.filter(user_id=user_id, usage_date__gte=start)
    include_cost = P.is_admin(request.user) or (
        str(request.user.id) == str(user_id) and P.student_can_view_cost()
    )
    return Response({
        "user_id": int(user_id),
        "month": _totals(qs, include_cost),
        "today": _totals(qs.filter(usage_date=today), include_cost),
    })


@api_view(["GET"])
@permission_classes([P.IsAdminRole])
def features(request):
    today = timezone.localdate()
    date_from = _parse_date(request.query_params.get("date_from"), today - timedelta(days=30))
    date_to = _parse_date(request.query_params.get("date_to"), today)
    return Response(list(usage_logger.get_feature_usage(date_from, date_to)))


@api_view(["GET"])
@permission_classes([P.IsAdminRole])
def models(request):
    today = timezone.localdate()
    date_from = _parse_date(request.query_params.get("date_from"), today - timedelta(days=30))
    date_to = _parse_date(request.query_params.get("date_to"), today)
    return Response(list(usage_logger.get_model_usage(date_from, date_to)))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def limits_me(request):
    """The caller's own daily AI-Tutor limit (remaining minutes). No cost."""
    row = limit_service.get_student_daily_limit(request.user)
    return Response(StudentDailyAILimitSerializer(row).data)


@api_view(["POST"])
@permission_classes([P.IsAdminRole])
def recalculate(request):
    """Admin-only: rebuild daily summaries for a date (default today)."""
    date = _parse_date(request.data.get("date") if hasattr(request, "data") else None,
                       timezone.localdate())
    written = aggregation.recalculate_day(date)
    return Response({"date": str(date), "summaries_written": written})
