"""Write & query ``AIUsageLog`` rows.

The single place rows are created. The wrapper calls ``log_ai_usage``; tests
and migrations may call the ``log_success`` / ``log_failure`` shortcuts.

Rules:
* ``request_id`` (when supplied) de-duplicates — a second call with the same
  id updates the existing row instead of double counting.
* Failed & cancelled requests are logged.
* No raw prompts/responses unless settings explicitly enable it; metadata is
  redacted by default.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .. import constants as C
from ..models import AIUsageLog
from . import cost_calculator

logger = logging.getLogger(__name__)

# Keys that must never be persisted in metadata.
_SENSITIVE_KEYS = {
    "api_key", "authorization", "auth", "token", "secret", "password",
    "ai_api_key", "bearer", "client_secret", "key", "prompt", "messages",
    "response", "content", "input", "output", "text", "transcript",
}


def _resolve_role(user, role: str | None) -> str:
    if role:
        return role
    if user is None or not getattr(user, "is_authenticated", False):
        return C.ROLE_SYSTEM
    profile = getattr(user, "profile", None)
    if profile is None:
        return C.ROLE_STUDENT
    try:
        if profile.is_admin:
            return C.ROLE_ADMIN
        if profile.is_teacher and not profile.is_student:
            return C.ROLE_TEACHER
    except Exception:  # pragma: no cover - defensive
        pass
    return C.ROLE_STUDENT


def redact_metadata(metadata: dict | None) -> dict:
    """Strip sensitive keys + cap size. Always returns a safe dict."""
    if not metadata:
        return {}
    if not getattr(settings, "AI_USAGE_REDACT_METADATA", True):
        return dict(metadata)
    clean: dict = {}
    for key, value in metadata.items():
        if str(key).lower() in _SENSITIVE_KEYS:
            continue
        if isinstance(value, str) and len(value) > 200:
            value = value[:200] + "…"
        clean[key] = value
    return clean


def log_ai_usage(
    *,
    user=None,
    role: str | None = None,
    feature: str = C.FEATURE_OTHER,
    provider: str = C.PROVIDER_OPENAI,
    model_name: str = "",
    status: str = C.STATUS_SUCCESS,
    input_tokens: int = 0,
    output_tokens: int = 0,
    audio_input_seconds: int = 0,
    audio_output_seconds: int = 0,
    ai_minutes_used=None,
    estimated_cost_usd=None,
    request_id: str | None = None,
    session_id: str = "",
    lesson_id: int | None = None,
    unit_id: int | None = None,
    course_id: int | None = None,
    organization: str = "",
    error_message: str = "",
    latency_ms: int | None = None,
    metadata: dict | None = None,
) -> AIUsageLog:
    """Create (or, on duplicate ``request_id``, update) one usage row.

    Cost is computed from ``AIModelPricing`` when not supplied. Never raises:
    a logging failure must not break the AI response path.
    """
    input_tokens = int(input_tokens or 0)
    output_tokens = int(output_tokens or 0)
    total_tokens = input_tokens + output_tokens
    audio_input_seconds = int(audio_input_seconds or 0)
    audio_output_seconds = int(audio_output_seconds or 0)

    if estimated_cost_usd is None:
        estimated_cost_usd = cost_calculator.calculate_total_cost(
            provider, model_name,
            input_tokens=input_tokens, output_tokens=output_tokens,
            audio_input_seconds=audio_input_seconds,
            audio_output_seconds=audio_output_seconds,
        )
    else:
        estimated_cost_usd = cost_calculator.safe_decimal(estimated_cost_usd)

    if ai_minutes_used is None:
        ai_minutes_used = Decimal("0")
    else:
        ai_minutes_used = cost_calculator.safe_decimal(ai_minutes_used)

    role = _resolve_role(user, role)
    user_obj = user if (user is not None and getattr(user, "is_authenticated", False)) else None

    fields = dict(
        user=user_obj,
        organization=organization or "",
        role=role,
        feature=feature,
        provider=provider,
        model_name=model_name or "",
        status=status,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        audio_input_seconds=audio_input_seconds,
        audio_output_seconds=audio_output_seconds,
        ai_minutes_used=ai_minutes_used,
        estimated_cost_usd=estimated_cost_usd,
        session_id=session_id or "",
        lesson_id=lesson_id,
        unit_id=unit_id,
        course_id=course_id,
        error_message=(error_message or "")[:500],
        latency_ms=latency_ms,
        usage_date=timezone.localdate(),
        metadata=redact_metadata(metadata),
    )

    try:
        if request_id:
            obj, _created = AIUsageLog.objects.update_or_create(
                request_id=request_id, defaults=fields,
            )
            return obj
        return AIUsageLog.objects.create(request_id=None, **fields)
    except Exception:  # pragma: no cover - logging must never break callers
        logger.exception("ai_usage.usage_logger: failed to write AIUsageLog")
        # Return an unsaved instance so callers relying on a return value
        # don't crash; it simply isn't persisted.
        return AIUsageLog(**fields)


def log_success(**kwargs) -> AIUsageLog:
    kwargs["status"] = C.STATUS_SUCCESS
    return log_ai_usage(**kwargs)


def log_failure(*, error_message: str = "", **kwargs) -> AIUsageLog:
    kwargs["status"] = C.STATUS_FAILED
    kwargs["error_message"] = error_message
    return log_ai_usage(**kwargs)


# --- queries ------------------------------------------------------------

def get_usage_for_user_day(user, date=None):
    date = date or timezone.localdate()
    return AIUsageLog.objects.filter(user=user, usage_date=date)


def get_feature_usage(date_from, date_to):
    from django.db.models import Count, Sum
    return (
        AIUsageLog.objects.filter(usage_date__gte=date_from, usage_date__lte=date_to)
        .values("feature")
        .annotate(
            requests=Count("id"),
            tokens=Sum("total_tokens"),
            cost=Sum("estimated_cost_usd"),
            minutes=Sum("ai_minutes_used"),
        )
        .order_by("-cost")
    )


def get_model_usage(date_from, date_to):
    from django.db.models import Count, Sum
    return (
        AIUsageLog.objects.filter(usage_date__gte=date_from, usage_date__lte=date_to)
        .values("provider", "model_name")
        .annotate(
            requests=Count("id"),
            tokens=Sum("total_tokens"),
            cost=Sum("estimated_cost_usd"),
        )
        .order_by("-cost")
    )
