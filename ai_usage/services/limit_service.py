"""Daily AI-Tutor minute enforcement.

This is a thin ADAPTER over the authoritative ``subscriptions`` quota
system (``quota_service`` + ``session_service``). It does not re-implement
minute accounting; it projects it into ``StudentDailyAILimit`` (a cache the
dashboard / API can read cheaply) and exposes a friendly bilingual gate.

Business rules (sourced from ``subscriptions``):
* New student → one-shot free trial of ``AI_TUTOR_FREE_FIRST_DAY_MINUTES``
  (default 5), granted ONCE and never reset (``FreeTrialUsage``).
* Base monthly plan → ``SubscriptionPlan.ai_tutor_daily_minutes`` (5).
* Upgrades → 10 / 20 / 30 minutes/day (plan-driven, admin-editable).
* Minutes are charged from ACTUAL session duration, not tokens.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.utils import timezone

from ..models import StudentDailyAILimit

logger = logging.getLogger(__name__)

_TWO_DP = Decimal("0.01")


def _minutes(seconds) -> Decimal:
    return (Decimal(int(seconds or 0)) / Decimal(60)).quantize(_TWO_DP, rounding=ROUND_HALF_UP)


# Bilingual message shown when the daily allowance is exhausted.
BLOCK_MESSAGE = {
    "ar": "لقد انتهى رصيدك اليومي من دقائق المعلم الذكي. يمكنك المتابعة غدًا أو ترقية الباقة.",
    "en": "Your daily AI Tutor minutes are finished. You can continue tomorrow or upgrade your plan.",
}


def _quota():
    """Lazy import so ai_usage stays importable even if subscriptions is mid-migration."""
    from subscriptions.services import quota_service
    return quota_service


def _subscription_service():
    from subscriptions.services import subscription_service
    return subscription_service


# --- read helpers -------------------------------------------------------

def get_allowed_minutes_for_student(student, date=None) -> Decimal:
    """Total AI-Tutor minutes the student is entitled to today.

    Subscription plan minutes when subscribed; otherwise the one-shot free
    trial grant (ensuring it exists). 0 when neither applies.
    """
    try:
        q = _quota()
        plan = _subscription_service().active_plan_for(student)
        if plan is not None:
            return _minutes(q.daily_ai_tutor_limit_seconds(student))
        # No paid plan → ensure the one-shot free trial exists, then report it.
        trial = q.get_or_create_free_trial(student)
        return _minutes(trial.free_seconds_granted)
    except Exception:
        logger.warning("limit_service: allowed-minutes lookup failed", exc_info=True)
        return Decimal(getattr(settings, "AI_TUTOR_BASE_DAILY_MINUTES", 5))


def get_remaining_minutes(student, date=None) -> Decimal:
    """Remaining AI-Tutor minutes right now. Never negative (display-safe)."""
    try:
        seconds, _source = _quota().effective_ai_tutor_remaining(student)
        return _minutes(max(0, seconds))
    except Exception:
        logger.warning("limit_service: remaining-minutes lookup failed", exc_info=True)
        return Decimal("0")


def _effective_source(student) -> str:
    try:
        _seconds, source = _quota().effective_ai_tutor_remaining(student)
        return source
    except Exception:
        return "none"


# --- projection row -----------------------------------------------------

def create_or_update_daily_limit(student, date=None) -> StudentDailyAILimit:
    """Build / refresh the student's ``StudentDailyAILimit`` row for today."""
    date = date or timezone.localdate()
    q = _quota()

    plan = None
    try:
        plan = _subscription_service().active_plan_for(student)
    except Exception:
        logger.warning("limit_service: active_plan_for failed", exc_info=True)

    is_free_first_day = False
    if plan is not None:
        # Subscription bucket. ``remaining`` is allowed − used within THIS
        # bucket (self-consistent, never negative). Note the subscriptions
        # layer may still grant a separate one-shot trial cushion — that is
        # reflected in the start gate (``check_can_start_ai_tutor``), not in
        # this per-plan projection.
        plan_name = getattr(plan, "name_en", "") or getattr(plan, "code", "")
        allowed_seconds = q.daily_ai_tutor_limit_seconds(student)
        used_seconds = q.get_or_create_today_quota(student).ai_tutor_seconds_used
        remaining_seconds = max(0, allowed_seconds - used_seconds)
    else:
        # Free-trial path (one-shot). Ensure the grant exists exactly once.
        trial = q.get_or_create_free_trial(student)
        plan_name = "free_trial"
        allowed_seconds = trial.free_seconds_granted
        used_seconds = trial.free_seconds_used
        remaining_seconds = trial.remaining_seconds
        is_free_first_day = True

    allowed = _minutes(allowed_seconds)
    used = _minutes(used_seconds)
    remaining = _minutes(max(0, remaining_seconds))

    row, _created = StudentDailyAILimit.objects.update_or_create(
        student=student, date=date,
        defaults=dict(
            plan_name=plan_name[:128],
            allowed_minutes=allowed,
            used_minutes=used,
            remaining_minutes=remaining,
            is_free_first_day=is_free_first_day,
            is_exceeded=(remaining <= 0 and allowed > 0),
        ),
    )
    return row


def get_student_daily_limit(student, date=None) -> StudentDailyAILimit:
    """Return today's projection row, refreshing it from source first."""
    return create_or_update_daily_limit(student, date)


# --- gating -------------------------------------------------------------

def check_can_start_ai_tutor(student) -> tuple[bool, dict]:
    """Can this student begin an AI-Tutor session right now?

    Returns ``(allowed, info)``. ``info`` always carries bilingual ``message``
    and a machine ``reason`` so the UI can render either language.
    """
    try:
        allowed = _quota().can_user_start_ai_tutor_now(student)
    except Exception:
        logger.warning("limit_service: can_start lookup failed", exc_info=True)
        allowed = False
    if allowed:
        return True, {"reason": "ok", "message": {"ar": "", "en": ""}}
    return False, {"reason": "daily_minutes_exhausted", "message": dict(BLOCK_MESSAGE)}


def reserve_ai_tutor_minutes(student, estimated_minutes=None) -> tuple[bool, dict]:
    """Soft reservation: the underlying system charges on session end, so this
    is just a pre-flight gate. Mirrors ``check_can_start_ai_tutor``."""
    return check_can_start_ai_tutor(student)


def finalize_ai_tutor_minutes(student, actual_minutes) -> StudentDailyAILimit:
    """Charge ``actual_minutes`` of session time, then refresh the projection.

    Charges via the subscriptions bucket (subscription first, trial fallback)
    so the single source of truth stays consistent.
    """
    minutes = Decimal(str(actual_minutes or 0))
    seconds = int((minutes * Decimal(60)).to_integral_value(rounding=ROUND_HALF_UP))
    if seconds > 0:
        try:
            _quota().deduct_session_seconds(student, seconds)
        except Exception:
            logger.warning("limit_service: deduct_session_seconds failed", exc_info=True)
    return create_or_update_daily_limit(student)
