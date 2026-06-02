"""Roll ``AIUsageLog`` rows up into ``AIDailyUsageSummary``.

Idempotent: running for the same day twice produces the same summary (it
``update_or_create``s per (date, user, organization, role) group).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from .. import constants as C
from ..models import AIDailyUsageSummary, AIUsageLog


def _top(counter: dict) -> dict:
    if not counter:
        return {}
    key = max(counter, key=lambda k: counter[k])
    return {"name": key, "cost": str(counter[key])}


def aggregate_day(date) -> int:
    """Aggregate one calendar day. Returns the number of summary rows written."""
    logs = AIUsageLog.objects.filter(usage_date=date)
    # Group by (user_id, organization, role).
    groups: dict[tuple, list] = defaultdict(list)
    for log in logs.iterator():
        groups[(log.user_id, log.organization or "", log.role)].append(log)

    written = 0
    for (user_id, organization, role), rows in groups.items():
        feature_cost: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        model_cost: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        agg = dict(
            total_requests=0, successful_requests=0, failed_requests=0,
            input_tokens=0, output_tokens=0, total_tokens=0,
            ai_minutes_used=Decimal("0"), estimated_cost_usd=Decimal("0"),
            ai_tutor_minutes_used=Decimal("0"), placement_minutes_used=Decimal("0"),
            content_generation_cost=Decimal("0"),
        )
        for r in rows:
            agg["total_requests"] += 1
            if r.status == C.STATUS_SUCCESS:
                agg["successful_requests"] += 1
            elif r.status == C.STATUS_FAILED:
                agg["failed_requests"] += 1
            agg["input_tokens"] += r.input_tokens
            agg["output_tokens"] += r.output_tokens
            agg["total_tokens"] += r.total_tokens
            agg["ai_minutes_used"] += r.ai_minutes_used
            agg["estimated_cost_usd"] += r.estimated_cost_usd
            if r.feature == C.FEATURE_AI_TUTOR:
                agg["ai_tutor_minutes_used"] += r.ai_minutes_used
            if r.feature in (C.FEATURE_PLACEMENT_SPEAKING, C.FEATURE_PLACEMENT_WRITTEN):
                agg["placement_minutes_used"] += r.ai_minutes_used
            if r.feature == C.FEATURE_CONTENT_GENERATION:
                agg["content_generation_cost"] += r.estimated_cost_usd
            feature_cost[r.feature] += r.estimated_cost_usd
            model_cost[r.model_name or "unknown"] += r.estimated_cost_usd

        defaults = dict(agg)
        defaults["top_feature"] = _top(feature_cost)
        defaults["top_model"] = _top(model_cost)

        AIDailyUsageSummary.objects.update_or_create(
            date=date,
            user_id=user_id,
            organization=organization,
            role=role,
            defaults=defaults,
        )
        written += 1
    return written


def aggregate_range(date_from, date_to) -> int:
    total = 0
    cur = date_from
    one_day = timezone.timedelta(days=1)
    while cur <= date_to:
        total += aggregate_day(cur)
        cur = cur + one_day
    return total


def recalculate_day(date) -> int:
    """Drop existing summaries for the day and rebuild (true recalculation)."""
    AIDailyUsageSummary.objects.filter(date=date).delete()
    return aggregate_day(date)
