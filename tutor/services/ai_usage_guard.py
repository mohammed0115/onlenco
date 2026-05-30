"""Guardrails for AI calls inside the Challenge.

Two levels of protection:

  1. **Feature flag** — `CHALLENGE_AI_ENABLED` setting. False disables ALL
     Phase-7 AI calls site-wide; the UI still works (fallback path).

  2. **Quotas** — per session and per day, recorded in
     `ChallengeAIInteraction`. Default ceilings are deliberately tight
     so a runaway tab can't burn the OpenAI bill.

Public API:
  * `can_call_challenge_ai(user, session, interaction_type)
        -> (allowed: bool, reason: str)`
  * `record_ai_call(user, session, question, answer, interaction_type,
        status, response_en, response_ar, error_code, metadata)
        -> ChallengeAIInteraction`
  * `get_remaining_ai_calls(user, session) -> dict`
"""
from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone


# ---------------------------------------------------------------------------
# Tunables — read DYNAMICALLY each call so @override_settings works in tests
# and operators can hot-reload limits without restarting workers.
# ---------------------------------------------------------------------------

# Defaults — exposed at module level for telemetry / templates that prefer
# constants. The functions below re-read settings on every invocation so an
# `@override_settings(...)` block flips behaviour without a reload.
CHALLENGE_AI_ENABLED = getattr(settings, "CHALLENGE_AI_ENABLED", True)
CHALLENGE_AI_MAX_CALLS_PER_SESSION = getattr(
    settings, "CHALLENGE_AI_MAX_CALLS_PER_SESSION", 5,
)
CHALLENGE_AI_DAILY_LIMIT_PER_USER = getattr(
    settings, "CHALLENGE_AI_DAILY_LIMIT_PER_USER", 30,
)
CHALLENGE_AI_MAX_ROLEPLAY_TURNS = getattr(
    settings, "CHALLENGE_AI_MAX_ROLEPLAY_TURNS", 5,
)


def _flag(name: str, default):
    return getattr(settings, name, default)


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------

def is_enabled() -> bool:
    """True when Phase-7 AI is allowed at all on this deploy."""
    return bool(_flag("CHALLENGE_AI_ENABLED", True)) and bool(_flag("AI_API_KEY", ""))


def can_call_challenge_ai(user, session, interaction_type: str) -> tuple[bool, str]:
    """Returns `(allowed, reason)`. `reason` is a short machine code
    suitable for telemetry / UI tooltips."""
    if not is_enabled():
        return False, "ai_disabled"

    from tutor.models import ChallengeAIInteraction

    session_cap = _flag("CHALLENGE_AI_MAX_CALLS_PER_SESSION", 5)
    daily_cap   = _flag("CHALLENGE_AI_DAILY_LIMIT_PER_USER", 30)

    # Per-session ceiling — protects against rapid clicks.
    if session is not None:
        session_count = ChallengeAIInteraction.objects.filter(
            user=user, session=session, status__in=("success",),
        ).count()
        if session_count >= session_cap:
            return False, "session_limit"

    # Per-day ceiling — protects the deploy's overall spend.
    since = timezone.now() - timedelta(hours=24)
    daily_count = ChallengeAIInteraction.objects.filter(
        user=user, status="success", created_at__gte=since,
    ).count()
    if daily_count >= daily_cap:
        return False, "daily_limit"

    return True, "ok"


def record_ai_call(
    *,
    user,
    session=None,
    question=None,
    answer=None,
    interaction_type: str,
    status: str = "success",
    response_en: str = "",
    response_ar: str = "",
    error_code: str = "",
    prompt_hash: str = "",
    tokens_used: int | None = None,
    latency_ms: int | None = None,
    metadata: dict | None = None,
):
    """Persist a row in `ChallengeAIInteraction`. Returns the row.

    Always succeeds — never raises. The caller is free to use this for
    both successful and failed/fallback paths."""
    from tutor.models import ChallengeAIInteraction
    return ChallengeAIInteraction.objects.create(
        user=user,
        session=session,
        question=question,
        challenge_answer=answer,
        interaction_type=interaction_type,
        status=status,
        response_en=response_en,
        response_ar=response_ar,
        error_code=error_code,
        prompt_hash=prompt_hash,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        metadata=metadata or {},
    )


def get_remaining_ai_calls(user, session=None) -> dict:
    """Cheap snapshot for the UI footer."""
    from tutor.models import ChallengeAIInteraction
    since = timezone.now() - timedelta(hours=24)
    daily_used = ChallengeAIInteraction.objects.filter(
        user=user, status="success", created_at__gte=since,
    ).count()
    session_used = 0
    if session is not None:
        session_used = ChallengeAIInteraction.objects.filter(
            user=user, session=session, status="success",
        ).count()
    return {
        "enabled": is_enabled(),
        "session_used":      session_used,
        "session_limit":     CHALLENGE_AI_MAX_CALLS_PER_SESSION,
        "session_remaining": max(0, CHALLENGE_AI_MAX_CALLS_PER_SESSION - session_used),
        "daily_used":        daily_used,
        "daily_limit":       CHALLENGE_AI_DAILY_LIMIT_PER_USER,
        "daily_remaining":   max(0, CHALLENGE_AI_DAILY_LIMIT_PER_USER - daily_used),
    }
