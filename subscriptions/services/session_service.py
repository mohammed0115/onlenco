"""AI-Tutor session lifecycle: open, close, abort.

This is the *server-side* truth about who's currently in a tutor session
and how much they've consumed. The browser is just the client — the
unique constraint on AITutorSession (partial: status='in_progress') is
what stops a user from opening two parallel sessions by refreshing.

Flow:
    start_session(user) → AITutorSession(status='in_progress')
    ...client uses voice/realtime endpoint...
    end_session(session_id, actual_seconds) → status='completed', quota deducted
    cancel_session(session_id)              → status='cancelled', no deduction
"""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import AITutorSession
from . import quota_service


logger = logging.getLogger(__name__)


class QuotaExhausted(Exception):
    """Raised when ``start_session`` finds zero remaining seconds."""


class ConcurrentSessionExists(Exception):
    """Raised when the user already has an in-progress session."""


STALE_SESSION_AGE_MINUTES = 10


def cancel_stale_sessions_for(user) -> int:
    """Auto-close any in-progress AITutorSession older than STALE_SESSION_AGE_MINUTES.

    Kept as a separate helper so cron / scheduled cleanups can still
    target only old rows. ``start_session`` itself uses the more
    aggressive ``_cancel_all_open_for`` policy below.
    """
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(minutes=STALE_SESSION_AGE_MINUTES)
    return (
        AITutorSession.objects
        .filter(user=user, status="in_progress", started_at__lte=cutoff)
        .update(status="cancelled", ended_at=timezone.now())
    )


def _cancel_all_open_for(user) -> int:
    """Close ANY in-progress session for this user, regardless of age.

    Rationale: a learner can only run one voice call at a time. When
    they click Start again after a crashed/abandoned previous call,
    the expected behavior is "start a new one" — not "blocked for 10
    minutes by a ghost". A 30-second-old in_progress row whose
    hang-up POST never fired is functionally indistinguishable from
    a 10-minute-old one, so we treat them the same.
    """
    from django.utils import timezone
    return (
        AITutorSession.objects
        .filter(user=user, status="in_progress")
        .update(status="cancelled", ended_at=timezone.now())
    )


@transaction.atomic
def start_session(
    user,
    *,
    source: str = "voice_call",
    voice: str = "",
    conversation_id: int | None = None,
    voice_profile=None,
    avatar_profile=None,
    skip_quota: bool = False,
) -> AITutorSession:
    """Open a new in-progress session, charging against quota at end.

    Raises ``QuotaExhausted`` if both subscription and trial are empty,
    UNLESS ``skip_quota=True`` — used by the placement-test voice call,
    which a brand-new student takes during onboarding before they have
    any subscription or trial minutes. The placement call is its own
    short, free assessment (capped server-side at
    AI_REALTIME_MAX_SESSION_SECONDS).

    **Concurrent-session policy**: any prior in_progress row for this
    user is force-cancelled here (zero deduction). The partial unique
    constraint then guarantees only the new row sits in_progress. The
    older "stale-after-10-minutes" gate fought browser crashes /
    closed tabs too hard — the user clicked Start, they get a Start.
    """
    _cancel_all_open_for(user)

    remaining_seconds, source_bucket = quota_service.effective_ai_tutor_remaining(user)
    if remaining_seconds <= 0 and not skip_quota:
        raise QuotaExhausted("No tutor seconds available.")
    try:
        return AITutorSession.objects.create(
            user=user,
            source=source,
            status="in_progress",
            quota_source=source_bucket,
            voice=voice or "",
            conversation_id=conversation_id,
            voice_profile=voice_profile,
            avatar_profile=avatar_profile,
        )
    except IntegrityError as exc:
        # Partial unique constraint hit — caller raced an existing open session.
        raise ConcurrentSessionExists("An AI-Tutor session is already in progress.") from exc


def cancel_open_session_for(user) -> bool:
    """Force-close the user's current open session WITHOUT deduction.

    Exposed via the cancel-stale API endpoint so the browser can recover
    from "concurrent_session" errors after a crashed previous call.
    """
    open_session = get_open_session(user)
    if open_session is None:
        return False
    cancel_session(open_session.pk)
    return True


def get_open_session(user) -> AITutorSession | None:
    return AITutorSession.objects.filter(user=user, status="in_progress").first()


@transaction.atomic
def end_session(session_id: int, *, actual_seconds: int, killed_by_quota: bool = False) -> AITutorSession:
    """Close a session, deduct quota, persist remaining.

    ``actual_seconds`` is the browser-reported duration (already clamped
    by the caller). We charge it to the SAME bucket the session was
    opened against — so a session opened against the free trial doesn't
    silently become a subscription deduction if the user subscribes
    mid-session.
    """
    session = AITutorSession.objects.select_for_update().get(pk=session_id)
    if session.status != "in_progress":
        # Idempotent: end_session called twice (network retry) → noop.
        return session
    seconds = max(0, int(actual_seconds or 0))
    if session.source == "placement_voice":
        # Placement speaking is onboarding and has its OWN quota — it must
        # NEVER deduct from the daily AI-Tutor minute allowance (Prompt
        # 16.6F). We still record the elapsed seconds for analytics, but
        # leave subscription / trial buckets untouched.
        remaining, _src = quota_service.effective_ai_tutor_remaining(session.user)
        charged_source = "none"
    else:
        remaining, charged_source = quota_service.deduct_session_seconds(
            session.user, seconds, source_hint=session.quota_source,
        )
    session.ended_at = timezone.now()
    session.duration_seconds = seconds
    session.consumed_seconds = seconds
    session.remaining_after_seconds = remaining
    session.quota_source = charged_source
    session.status = "killed_quota_exceeded" if killed_by_quota else "completed"
    session.save(update_fields=[
        "ended_at", "duration_seconds", "consumed_seconds",
        "remaining_after_seconds", "quota_source", "status",
    ])
    return session


@transaction.atomic
def cancel_session(session_id: int) -> AITutorSession:
    """Close a session without deducting (e.g. user never spoke)."""
    session = AITutorSession.objects.select_for_update().get(pk=session_id)
    if session.status != "in_progress":
        return session
    session.ended_at = timezone.now()
    session.status = "cancelled"
    session.save(update_fields=["ended_at", "status"])
    return session
