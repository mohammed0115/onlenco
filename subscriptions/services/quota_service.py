"""Per-user daily quota — read & deduct AI Tutor / library audio seconds.

Sprint 1 ships the foundation; the AI Tutor and Library Reader wire
into ``consume_ai_tutor_seconds`` / ``consume_library_seconds`` in
Sprint 2 once session lifecycle is implemented.

Daily-reset semantics: there is no scheduled "reset job". Each calendar
day gets a fresh UserDailyQuota row on first read — that's the natural
reset point. ``get_or_create_today_quota`` is idempotent.
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ..models import FreeTrialUsage, SubscriptionPlan, UserDailyQuota, UserSubscription
from . import subscription_service


FREE_TRIAL_SECONDS = 5 * 60


def _today():
    return timezone.localdate()


def get_or_create_today_quota(user) -> UserDailyQuota:
    quota, _ = UserDailyQuota.objects.get_or_create(
        user=user, date=_today(),
    )
    return quota


def daily_ai_tutor_limit_seconds(user) -> int:
    """Total AI-Tutor seconds the user is entitled to today.

    Returns 0 when the user has no active subscription. Sprint 2 will
    grant a one-shot free trial via a separate path so that this stays
    a pure subscription-driven number.
    """
    plan = subscription_service.active_plan_for(user)
    if plan is None:
        return 0
    return int(plan.ai_tutor_daily_minutes) * 60


def daily_library_limit_seconds(user) -> int:
    plan = subscription_service.active_plan_for(user)
    if plan is None:
        return 0
    return int(plan.library_audio_daily_minutes) * 60


def ai_tutor_session_cap_seconds(user) -> int:
    """Per-session AI-Tutor cap in seconds.

    The active plan's ``ai_tutor_session_cap_minutes`` wins when set (>0),
    so admins can shorten/lengthen a single call from the Control Center.
    When it is 0 (the default for all seeded plans) we fall back to the
    global ``AI_REALTIME_MAX_SESSION_SECONDS`` setting — so behaviour is
    unchanged unless an admin opts in to a per-plan cap.
    """
    from django.conf import settings
    default = int(getattr(settings, "AI_REALTIME_MAX_SESSION_SECONDS", 900))
    plan = subscription_service.active_plan_for(user)
    plan_cap = int(getattr(plan, "ai_tutor_session_cap_minutes", 0) or 0) if plan else 0
    return plan_cap * 60 if plan_cap > 0 else default


def library_session_cap_seconds(user) -> int:
    """Per-session Library reading/listening cap in seconds (read-only today).

    Mirrors ``ai_tutor_session_cap_seconds``: the plan value wins, else the
    global ``LIBRARY_MAX_SESSION_SECONDS`` setting. The Library reader wires
    this in 19.0 — the value is already plan-driven and admin-editable now.
    """
    from django.conf import settings
    default = int(getattr(settings, "LIBRARY_MAX_SESSION_SECONDS", 900))
    plan = subscription_service.active_plan_for(user)
    plan_cap = int(getattr(plan, "library_session_cap_minutes", 0) or 0) if plan else 0
    return plan_cap * 60 if plan_cap > 0 else default


def get_remaining_ai_tutor_seconds(user) -> int:
    limit = daily_ai_tutor_limit_seconds(user)
    if limit == 0:
        return 0
    quota = get_or_create_today_quota(user)
    return max(0, limit - quota.ai_tutor_seconds_used)


def get_remaining_library_seconds(user) -> int:
    limit = daily_library_limit_seconds(user)
    if limit == 0:
        return 0
    quota = get_or_create_today_quota(user)
    return max(0, limit - quota.library_seconds_used)


def can_user_start_ai_tutor(user) -> bool:
    return get_remaining_ai_tutor_seconds(user) > 0


def can_user_start_library_audio(user) -> bool:
    return get_remaining_library_seconds(user) > 0


@transaction.atomic
def consume_ai_tutor_seconds(user, seconds: int) -> int:
    """Add ``seconds`` to today's AI-Tutor counter, returning the new remaining.

    Capped at the daily limit — over-spend is clamped (the caller is
    responsible for hard-stopping the session before this is reached).
    Returns the remaining seconds AFTER the deduction.
    """
    if seconds <= 0:
        return get_remaining_ai_tutor_seconds(user)
    limit = daily_ai_tutor_limit_seconds(user)
    if limit == 0:
        return 0
    quota = UserDailyQuota.objects.select_for_update().get_or_create(
        user=user, date=_today(),
    )[0]
    new_used = min(quota.ai_tutor_seconds_used + seconds, limit)
    if new_used != quota.ai_tutor_seconds_used:
        quota.ai_tutor_seconds_used = new_used
        quota.save(update_fields=["ai_tutor_seconds_used", "updated_at"])
    return max(0, limit - new_used)


@transaction.atomic
def consume_library_seconds(user, seconds: int) -> int:
    if seconds <= 0:
        return get_remaining_library_seconds(user)
    limit = daily_library_limit_seconds(user)
    if limit == 0:
        return 0
    quota = UserDailyQuota.objects.select_for_update().get_or_create(
        user=user, date=_today(),
    )[0]
    new_used = min(quota.library_seconds_used + seconds, limit)
    if new_used != quota.library_seconds_used:
        quota.library_seconds_used = new_used
        quota.save(update_fields=["library_seconds_used", "updated_at"])
    return max(0, limit - new_used)


def quota_snapshot(user) -> dict:
    """Single dict suited for the user's tutor/library UI."""
    quota = get_or_create_today_quota(user)
    plan = subscription_service.active_plan_for(user)
    ai_limit = daily_ai_tutor_limit_seconds(user)
    lib_limit = daily_library_limit_seconds(user)
    trial_remaining = get_free_trial_remaining_seconds(user)
    return {
        "plan_code": plan.code if plan else None,
        "plan_name_en": plan.name_en if plan else None,
        "plan_name_ar": plan.name_ar if plan else None,
        "date": quota.date,
        "ai_tutor": {
            "limit_seconds": ai_limit,
            "used_seconds": quota.ai_tutor_seconds_used,
            "remaining_seconds": max(0, ai_limit - quota.ai_tutor_seconds_used),
        },
        "library_audio": {
            "limit_seconds": lib_limit,
            "used_seconds": quota.library_seconds_used,
            "remaining_seconds": max(0, lib_limit - quota.library_seconds_used),
        },
        "free_trial": {
            "remaining_seconds": trial_remaining,
            "is_consumed": trial_remaining == 0,
        },
    }


# ---------------------------------------------------------------------------
# Free trial (one-shot, never resets)
# ---------------------------------------------------------------------------

def get_or_create_free_trial(user) -> FreeTrialUsage:
    """Ensure the user has a trial row. The grant defaults to FREE_TRIAL_SECONDS."""
    trial, _ = FreeTrialUsage.objects.get_or_create(
        user=user,
        defaults={"free_seconds_granted": FREE_TRIAL_SECONDS},
    )
    return trial


def get_free_trial_remaining_seconds(user) -> int:
    trial = FreeTrialUsage.objects.filter(user=user).first()
    if trial is None:
        return 0
    return trial.remaining_seconds


@transaction.atomic
def consume_free_trial_seconds(user, seconds: int) -> int:
    """Spend ``seconds`` from the trial bucket. Returns remaining trial seconds."""
    if seconds <= 0:
        return get_free_trial_remaining_seconds(user)
    trial = FreeTrialUsage.objects.select_for_update().filter(user=user).first()
    if trial is None:
        return 0
    new_used = min(trial.free_seconds_used + seconds, trial.free_seconds_granted)
    if new_used != trial.free_seconds_used:
        trial.free_seconds_used = new_used
        if new_used >= trial.free_seconds_granted and not trial.is_consumed:
            trial.is_consumed = True
            trial.consumed_at = timezone.now()
            trial.save(update_fields=["free_seconds_used", "is_consumed", "consumed_at", "updated_at"])
        else:
            trial.save(update_fields=["free_seconds_used", "updated_at"])
    return max(0, trial.free_seconds_granted - new_used)


# ---------------------------------------------------------------------------
# Unified "entitled to tutor right now?" — subscription first, trial fallback
# ---------------------------------------------------------------------------

def effective_ai_tutor_remaining(user) -> tuple[int, str]:
    """How many AI-Tutor seconds the user can spend right now + the source.

    Returns ``(seconds, source)`` where source ∈ ``{"subscription", "free_trial", "none"}``.
    Subscription wins when active (so paid users don't accidentally burn the trial).
    """
    sub_seconds = get_remaining_ai_tutor_seconds(user)
    if sub_seconds > 0:
        return sub_seconds, "subscription"
    trial_seconds = get_free_trial_remaining_seconds(user)
    if trial_seconds > 0:
        return trial_seconds, "free_trial"
    return 0, "none"


def can_user_start_ai_tutor_now(user) -> bool:
    seconds, _ = effective_ai_tutor_remaining(user)
    return seconds > 0


@transaction.atomic
def deduct_session_seconds(user, seconds: int, source_hint: str | None = None) -> tuple[int, str]:
    """Charge ``seconds`` to the right bucket, returning ``(remaining, source)``.

    ``source_hint`` lets the caller force the bucket (e.g. when ending a
    session that was opened against the trial — we want to keep deducting
    from the trial even if a subscription was created mid-session).
    """
    if seconds <= 0:
        seconds, src = effective_ai_tutor_remaining(user)
        return seconds, src
    if source_hint == "free_trial":
        remaining = consume_free_trial_seconds(user, seconds)
        return remaining, "free_trial"
    if source_hint == "subscription":
        remaining = consume_ai_tutor_seconds(user, seconds)
        return remaining, "subscription"
    # No hint: charge subscription if it has any allowance today; else trial.
    if daily_ai_tutor_limit_seconds(user) > 0:
        remaining = consume_ai_tutor_seconds(user, seconds)
        return remaining, "subscription"
    remaining = consume_free_trial_seconds(user, seconds)
    return remaining, "free_trial"
