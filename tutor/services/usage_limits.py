"""The single official entry point for AI-Tutor usage limits (Prompt 17.1 / 17.2).

This is a thin FACADE over the existing subscriptions quota/session services.
It does NOT re-implement accounting — the buckets (subscription vs free trial),
daily-reset semantics, and the concurrent-session constraint all stay in
``subscriptions`` as the single source of truth. What this module adds:

    * ONE place every AI-Tutor endpoint asks "allowed / used / left today?",
      "may this student start?", and "charge what they actually used";
    * explicit MODES, so a placement speaking call can never touch the paid
      daily AI-Tutor minutes, and a text message never silently burns voice
      minutes unless product config says so;
    * idempotent voice-message deduction, so a retried request can't double-bill.

Before this facade, enforcement was split across three different sources of
truth (core.services.ai_usage for text, subscriptions for calls, and nothing
for voice messages). New/changed endpoints must go through here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from subscriptions.models import FreeTrialUsage, UserDailyQuota
from subscriptions.services import quota_service, session_service
# Re-exported so callers can ``except usage_limits.QuotaExhausted``.
from subscriptions.services.session_service import (  # noqa: F401
    ConcurrentSessionExists,
    QuotaExhausted,
)


# ---------------------------------------------------------------------------
# Modes — the explicit contract that keeps placement out of paid minutes.
# ---------------------------------------------------------------------------
MODE_PLACEMENT_SPEAKING_CALL = "placement_speaking_call"
MODE_REGULAR_AI_TUTOR_CALL = "regular_ai_tutor_call"
MODE_REGULAR_AI_TUTOR_MESSAGE = "regular_ai_tutor_message"
MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE = "regular_ai_tutor_voice_message"

REGULAR_MODES = frozenset({
    MODE_REGULAR_AI_TUTOR_CALL,
    MODE_REGULAR_AI_TUTOR_MESSAGE,
    MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE,
})
ALL_MODES = REGULAR_MODES | {MODE_PLACEMENT_SPEAKING_CALL}

# Modes whose seconds are charged against the daily AI-Tutor allowance.
# A live call and any voice message always consume; placement never does.
_ALWAYS_CONSUMING_MODES = frozenset({
    MODE_REGULAR_AI_TUTOR_CALL,
    MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE,
})

# Only call-style modes open a long-lived AITutorSession row (with the
# one-in-progress constraint). Discrete messages must NOT, or they would
# cancel a live call's session. Maps mode -> AITutorSession.source.
_SESSION_SOURCE = {
    MODE_PLACEMENT_SPEAKING_CALL: "placement_voice",
    MODE_REGULAR_AI_TUTOR_CALL: "voice_call",
}


def _min_start_seconds() -> int:
    """Least remaining time we require before letting a paid interaction begin."""
    return int(getattr(settings, "TUTOR_MIN_START_SECONDS", 5))


def _voice_message_fallback_seconds() -> int:
    """Conservative charge when a voice message has no reliable duration."""
    return int(getattr(settings, "TUTOR_VOICE_MESSAGE_FALLBACK_SECONDS", 10))


def is_valid_mode(mode: str) -> bool:
    return mode in ALL_MODES


def is_placement_mode(mode: str) -> bool:
    return mode == MODE_PLACEMENT_SPEAKING_CALL


def is_minute_bearing_mode(mode: str) -> bool:
    """Whether ``mode`` charges against the daily AI-Tutor allowance.

    Text-only messages are tracked separately and do NOT consume voice
    minutes unless ``TUTOR_TEXT_MESSAGE_CONSUMES_MINUTES`` is explicitly set.
    """
    if mode in _ALWAYS_CONSUMING_MODES:
        return True
    if mode == MODE_REGULAR_AI_TUTOR_MESSAGE:
        return bool(getattr(settings, "TUTOR_TEXT_MESSAGE_CONSUMES_MINUTES", False))
    return False  # placement_speaking_call


# Backwards-compatible alias (Prompt 17.1 naming).
mode_consumes_minutes = is_minute_bearing_mode


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class UsageLimitError(Exception):
    """Raised when a student has no (or too little) daily AI-Tutor time left."""

    def __init__(self, *, remaining: int = 0):
        self.remaining = int(remaining)
        self.message_ar = "انتهى وقت المساعد الذكي اليومي في خطتك."
        self.message_en = "Your daily AI tutor time is used up."
        super().__init__(self.message_en)

    @property
    def info(self) -> dict:
        return {
            "reason": "daily_minutes_exhausted",
            "remaining_seconds": self.remaining,
            "message": {"ar": self.message_ar, "en": self.message_en},
        }


# ---------------------------------------------------------------------------
# Read API
# ---------------------------------------------------------------------------
def get_daily_allowed_seconds(student) -> int:
    """Seconds the student is entitled to today.

    Subscription allowance when on a paid plan; otherwise the one-shot free
    trial grant. We only touch the trial bucket when there is no plan, so a
    paid student never has their plan silently topped up by trial seconds.
    """
    sub = quota_service.daily_ai_tutor_limit_seconds(student)
    if sub > 0:
        return int(sub)
    trial = quota_service.get_or_create_free_trial(student)
    return int(trial.free_seconds_granted)


def get_daily_used_seconds(student, date=None) -> int:
    """Seconds already consumed by ``student`` on the given local day.

    Per-day rows mean a new calendar day naturally reports 0 used (the daily
    reset). The trial bucket is one-shot (not per-day), so it is only reported
    when the student has no paid allowance.
    """
    day = date or timezone.localdate()
    row = UserDailyQuota.objects.filter(user=student, date=day).first()
    used_sub = int(row.ai_tutor_seconds_used) if row else 0
    if quota_service.daily_ai_tutor_limit_seconds(student) > 0:
        return used_sub
    trial = FreeTrialUsage.objects.filter(user=student).first()
    return int(trial.free_seconds_used) if trial else 0


def get_remaining_seconds(student, date=None) -> int:
    """Seconds the student may still spend on the given local day.

    Computed as ``allowed - used`` on ONE consistent bucket: the paid plan when
    subscribed, otherwise the free trial. We deliberately do NOT use the
    subscriptions ``effective_ai_tutor_remaining`` here, because that falls back
    to leftover free-trial seconds once a paid plan is exhausted — which would
    let a plan run past its daily cap (breaking rules 5/6). Unifying on
    allowed-minus-used is the whole point of this facade.
    """
    return max(0, get_daily_allowed_seconds(student) - get_daily_used_seconds(student, date))


def usage_snapshot(student) -> dict:
    """Compact view for the call/message UI timer."""
    return {
        "allowed_seconds": get_daily_allowed_seconds(student),
        "used_seconds": get_daily_used_seconds(student),
        "remaining_seconds": get_remaining_seconds(student),
        "min_start_seconds": _min_start_seconds(),
    }


# ---------------------------------------------------------------------------
# Gating
# ---------------------------------------------------------------------------
def can_start_ai_tutor_usage(student, mode, requested_seconds=None) -> bool:
    """True when ``student`` may begin ``mode`` right now.

    Non-minute-bearing modes (placement, plain text unless configured) always
    pass. Minute-bearing modes require at least the configured minimum time
    left (and, when given, the requested seconds are advisory — the live
    session is hard-capped to the remaining time by the caller).
    """
    if not is_minute_bearing_mode(mode):
        return True
    remaining = get_remaining_seconds(student)
    return remaining >= _min_start_seconds()


def assert_can_use_ai_tutor(student, mode, requested_seconds=None) -> int:
    """Raise ``UsageLimitError`` if the student can't begin ``mode``.

    Returns the remaining seconds on success. This is the backend gate every
    minute-bearing endpoint must call before doing AI work.
    """
    if not is_minute_bearing_mode(mode):
        return get_remaining_seconds(student)
    if not can_start_ai_tutor_usage(student, mode, requested_seconds):
        raise UsageLimitError(remaining=get_remaining_seconds(student))
    return get_remaining_seconds(student)


# Backwards-compatible alias (Prompt 17.1 naming).
def enforce_limit_before_audio_or_call(student, mode=MODE_REGULAR_AI_TUTOR_CALL) -> int:
    return assert_can_use_ai_tutor(student, mode)


def can_start_regular_ai_tutor_session(student) -> bool:
    return can_start_ai_tutor_usage(student, MODE_REGULAR_AI_TUTOR_CALL)


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------
@dataclass
class Usage:
    """Handle returned by ``start_ai_tutor_usage`` and consumed by
    ``finalize_ai_tutor_usage``. Carries enough context to charge correctly."""

    ok: bool
    mode: str
    session_id: int | None
    consumes_minutes: bool
    remaining_seconds: int
    source: str
    student: object = None
    metadata: dict = field(default_factory=dict)


# Backwards-compatible alias name for the handle type.
Reservation = Usage


def start_ai_tutor_usage(student, mode, requested_seconds=None, source=None, metadata=None) -> Usage:
    """Reserve/begin a usage interaction and return a handle.

    * placement_speaking_call → opens a quota-free session (never deducts).
    * regular_ai_tutor_call    → asserts the limit, then opens a session row.
    * regular_ai_tutor_(voice_)message → asserts (if minute-bearing) and returns
      a session-less handle, so it can't cancel a live call's session.

    Raises ``UsageLimitError`` (minute-bearing mode out of time) or
    ``ConcurrentSessionExists`` (a session is already open).
    """
    if not is_valid_mode(mode):
        raise ValueError(f"Unknown usage mode: {mode!r}")
    meta = dict(metadata or {})

    if is_placement_mode(mode):
        session = session_service.start_session(
            student, source=source or _SESSION_SOURCE[mode], skip_quota=True,
        )
        return Usage(
            ok=True, mode=mode, session_id=session.pk, consumes_minutes=False,
            remaining_seconds=get_remaining_seconds(student), source="none",
            student=student, metadata=meta,
        )

    consumes = is_minute_bearing_mode(mode)
    if consumes:
        assert_can_use_ai_tutor(student, mode, requested_seconds)

    remaining, bucket = quota_service.effective_ai_tutor_remaining(student)
    if mode == MODE_REGULAR_AI_TUTOR_CALL:
        session = session_service.start_session(student, source=source or _SESSION_SOURCE[mode])
        return Usage(
            ok=True, mode=mode, session_id=session.pk, consumes_minutes=True,
            remaining_seconds=remaining, source=bucket, student=student, metadata=meta,
        )
    # message / voice_message: gate only, no session row.
    return Usage(
        ok=True, mode=mode, session_id=None, consumes_minutes=consumes,
        remaining_seconds=remaining, source=bucket, student=student, metadata=meta,
    )


def _session_id_of(usage_or_session) -> int | None:
    if usage_or_session is None:
        return None
    if isinstance(usage_or_session, Usage):
        return usage_or_session.session_id
    if isinstance(usage_or_session, int):
        return usage_or_session
    # An AITutorSession instance.
    return getattr(usage_or_session, "pk", None)


def finalize_ai_tutor_usage(usage_or_session, actual_seconds, metadata=None, killed_by_quota=False):
    """Finalise a usage interaction and charge the seconds actually used.

    Accepts a ``Usage`` handle, an ``AITutorSession`` (or its pk), or ``None``:

    * Session-backed (call / placement) → closes via the session service, which
      deducts unless the session is a placement call. ``end_session`` is
      idempotent (a second finalize of the same session is a no-op), so a
      duplicated hang-up log can't double-charge.
    * Session-less ``Usage`` (voice / text message) → charges directly, only
      when the mode is minute-bearing.
    """
    seconds = max(0, int(actual_seconds or 0))
    session_id = _session_id_of(usage_or_session)
    if session_id is not None:
        return session_service.end_session(
            session_id, actual_seconds=seconds, killed_by_quota=killed_by_quota,
        )

    if isinstance(usage_or_session, Usage):
        u = usage_or_session
        if u.consumes_minutes and u.student is not None and seconds > 0:
            return deduct_voice_message_usage(
                u.student, seconds, source=(u.source if u.source != "none" else None),
                metadata=metadata,
            )
    return None


# Backwards-compatible alias (Prompt 17.1 naming).
def finish_usage_session(session_id, actual_seconds, *, student=None, mode=None):
    if session_id is not None:
        return session_service.end_session(session_id, actual_seconds=max(0, int(actual_seconds or 0)))
    if student is not None and mode is not None and is_minute_bearing_mode(mode):
        return deduct_voice_message_usage(student, actual_seconds)
    return None


# Backwards-compatible alias (Prompt 17.1 naming).
reserve_or_start_usage_session = start_ai_tutor_usage


# ---------------------------------------------------------------------------
# Voice-message deduction (idempotent)
# ---------------------------------------------------------------------------
def remaining_and_source(student) -> tuple[int, str]:
    """Unified ``(remaining_seconds, bucket)`` for reporting — no deduction.

    Mirrors ``get_remaining_seconds`` (allowed-minus-used, no trial bleed) and
    names the active bucket, so endpoints never call ``effective_ai_tutor_remaining``
    directly for tutor reporting.
    """
    remaining = get_remaining_seconds(student)
    if quota_service.daily_ai_tutor_limit_seconds(student) > 0:
        return remaining, "subscription"
    trial_remaining = quota_service.get_free_trial_remaining_seconds(student)
    return remaining, ("free_trial" if trial_remaining > 0 else "none")


def deduct_usage_seconds(student, actual_seconds, source=None, idempotency_key=None, metadata=None):
    """Charge ``actual_seconds`` against the daily allowance, once (idempotent).

    Falls back to a conservative charge when no reliable duration is given. An
    ``idempotency_key`` (when provided) prevents a retried request from
    double-billing — deduped via the cache for one hour.

    Returns ``(remaining_seconds, source)``.
    """
    seconds = int(actual_seconds or 0)
    if seconds <= 0:
        seconds = _voice_message_fallback_seconds()
    seconds = max(0, seconds)

    if idempotency_key:
        cache_key = f"tutor:usage:{getattr(student, 'pk', student)}:{idempotency_key}"
        if cache.get(cache_key):
            return remaining_and_source(student)
        cache.set(cache_key, 1, timeout=3600)

    # source_hint must be a known bucket ("subscription"/"free_trial") or None.
    hint = source if source in ("subscription", "free_trial") else None
    return quota_service.deduct_session_seconds(student, seconds, source_hint=hint)


# A voice message is just a named use of the generic deduction.
deduct_voice_message_usage = deduct_usage_seconds
