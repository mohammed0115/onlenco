"""ModelRouter — the single entry point for AI tasks.

Calling code MUST go through `route_task(...)` rather than calling
OpenAI / a local LLM directly. The router enforces:

  * pipeline order — cheap deterministic providers first, OpenAI last
  * confidence thresholds — providers below the bar are skipped
  * fallback safety — exceptions are caught, logged, and the next
    provider is tried; the caller never sees an unhandled traceback
  * single point of audit — every call lands in `ModelPredictionLog`,
    so you can answer "how often did this task hit OpenAI last week?"
    with a single ORM query.

Public surface:
    route_task(task_type, input_data, user=None, context=None) -> dict

Return shape:
    {
      "provider": "rules|local_classifier|local_llm|rag|openai|none",
      "output": {...},
      "confidence": float,
      "fallback_used": bool,
      "reason": str,
      "model_version": str,
    }
"""
from __future__ import annotations

import logging
import time
from typing import Any

from django.conf import settings

from . import providers as _providers
from .. import constants as C
from ..models import ModelPredictionLog, ProviderKillSwitch

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Threshold helpers
# ---------------------------------------------------------------------------

def _threshold(provider: str) -> float:
    """Allow operators to override per-provider thresholds via settings."""
    overrides = getattr(settings, "AI_ROUTER_THRESHOLDS", {}) or {}
    if provider in overrides:
        try:
            return float(overrides[provider])
        except (TypeError, ValueError):
            pass
    return C.DEFAULT_THRESHOLDS.get(provider, 0.0)


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

def _is_disabled(task_type: str, provider: str) -> tuple[bool, str]:
    """True iff a `ProviderKillSwitch` row says skip this provider.

    Wildcard rows (task_type='*') apply to all tasks. Expired rows are
    treated as inactive — the operator can leave them in place for
    audit but the router stops respecting them once `expires_at` passes.
    """
    from django.utils import timezone
    rows = ProviderKillSwitch.objects.filter(
        provider=provider, disabled=True,
    ).filter(task_type__in=[task_type, "*"])
    now = timezone.now()
    for row in rows:
        if row.expires_at is None or row.expires_at > now:
            return True, row.reason or f"kill_switch:{row.task_type}"
    return False, ""


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _safe_user(user) -> Any | None:
    """Return a user instance only if it looks like a real, authenticated
    User row — anonymous / SimpleLazyObject placeholders log as None."""
    if user is None:
        return None
    if not getattr(user, "is_authenticated", False):
        return None
    return user


def _log(*, task_type, provider, confidence, fallback_used, latency_ms,
         success, user, error_message="", model_version="", reason="",
         metadata=None) -> ModelPredictionLog:
    return ModelPredictionLog.objects.create(
        task_type=task_type,
        provider=provider,
        confidence=float(confidence or 0.0),
        fallback_used=bool(fallback_used),
        latency_ms=int(max(0, latency_ms)),
        success=bool(success),
        user=_safe_user(user),
        error_message=(error_message or "")[:1000],
        model_version=(model_version or "")[:80],
        reason=(reason or "")[:120],
        metadata=metadata or {},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def route_task(
    task_type: str,
    input_data: dict | None = None,
    *,
    user=None,
    context: dict | None = None,
) -> dict:
    """Route `task_type` through its pipeline and return the first
    above-threshold result. Always returns the structured dict — even
    when every provider failed (caller can branch on `provider=='none'`)."""
    if task_type not in C.PIPELINES:
        return _empty(reason=f"unknown_task_type:{task_type}",
                      task_type=task_type, user=user)
    input_data = dict(input_data or {})
    pipeline = C.PIPELINES[task_type]

    overall_t0 = time.time()
    fallback_used = False
    last_error_msg = ""

    for provider_name in pipeline:
        provider_fn = _providers.PROVIDERS.get(provider_name)
        if provider_fn is None:
            fallback_used = True
            continue

        # Kill-switch check — operator-controlled disable per
        # (task_type, provider). Skipping is silent (no log) since this
        # is an operator decision, not a model failure.
        disabled, kill_reason = _is_disabled(task_type, provider_name)
        if disabled:
            fallback_used = True
            _log(
                task_type=task_type, provider=provider_name,
                confidence=0.0, fallback_used=True, latency_ms=0,
                success=False, user=user,
                reason=f"kill_switch:{kill_reason}",
            )
            continue

        t0 = time.time()
        result: dict | None = None
        error_msg = ""
        try:
            result = provider_fn(task_type, input_data, context)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            last_error_msg = error_msg
            logger.warning("provider %s raised on %s: %s",
                           provider_name, task_type, e)

        latency_ms = int((time.time() - t0) * 1000)

        # Provider raised → log the failure, mark fallback, move on.
        if error_msg:
            _log(
                task_type=task_type, provider=provider_name,
                confidence=0.0, fallback_used=True,
                latency_ms=latency_ms, success=False,
                user=user, error_message=error_msg,
                reason="provider_exception",
            )
            fallback_used = True
            continue

        # Provider opted out → no log, just move on.
        if result is None:
            fallback_used = True
            continue

        confidence = float(result.get("confidence") or 0.0)
        threshold = _threshold(provider_name)

        if confidence < threshold:
            # Above-zero confidence but below the bar — log as a failed
            # attempt so the operator can see how often this happens.
            _log(
                task_type=task_type, provider=provider_name,
                confidence=confidence, fallback_used=True,
                latency_ms=latency_ms, success=False,
                user=user,
                model_version=str(result.get("model_version") or ""),
                reason=f"below_threshold:{threshold}",
            )
            fallback_used = True
            continue

        # Success — log and return.
        total_latency = int((time.time() - overall_t0) * 1000)
        _log(
            task_type=task_type, provider=provider_name,
            confidence=confidence, fallback_used=fallback_used,
            latency_ms=total_latency, success=True, user=user,
            model_version=str(result.get("model_version") or ""),
            reason="ok",
        )
        return {
            "provider":      provider_name,
            "output":        result.get("output") or {},
            "confidence":    confidence,
            "fallback_used": fallback_used,
            "reason":        "ok",
            "model_version": str(result.get("model_version") or ""),
        }

    # No provider succeeded.
    total_latency = int((time.time() - overall_t0) * 1000)
    _log(
        task_type=task_type, provider=C.P_NONE,
        confidence=0.0, fallback_used=True,
        latency_ms=total_latency, success=False, user=user,
        error_message=last_error_msg,
        reason="all_providers_failed",
    )
    return {
        "provider":      C.P_NONE,
        "output":        {},
        "confidence":    0.0,
        "fallback_used": True,
        "reason":        "all_providers_failed",
        "model_version": "",
    }


def _empty(*, task_type: str, reason: str, user=None) -> dict:
    _log(
        task_type=task_type or "", provider=C.P_NONE,
        confidence=0.0, fallback_used=False, latency_ms=0,
        success=False, user=user, reason=reason,
    )
    return {
        "provider":      C.P_NONE,
        "output":        {},
        "confidence":    0.0,
        "fallback_used": False,
        "reason":        reason,
        "model_version": "",
    }
