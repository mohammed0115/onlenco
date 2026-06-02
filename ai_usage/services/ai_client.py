"""Centralised AI client wrapper — the single egress for ALL AI calls.

After migration, no view / task / service calls the provider directly; they
call one of the methods here. The wrapper:

  1. checks the tracking flag,
  2. enforces AI-Tutor daily minutes for speaking features,
  3. calls the configured OpenAI-compatible provider,
  4. captures tokens (chat) and audio duration (STT),
  5. prices the call via ``AIModelPricing`` (cost_calculator),
  6. writes an ``AIUsageLog`` for success / failure / cancellation,
  7. handles streaming safely,
  8. never logs or returns the API key,
  9. returns the provider response unchanged to the caller.

Transport mirrors the project's established pattern: raw HTTP to
``settings.AI_API_BASE`` with a ``Bearer`` token. For plain chat the wrapper
can delegate to ``factory.services.llm_router`` (local-first routing) when the
caller asks for it; otherwise it posts directly so usage is fully observable.
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal

import requests
from django.conf import settings

from .. import constants as C
from . import limit_service, usage_logger

logger = logging.getLogger(__name__)


class DailyMinutesExceeded(Exception):
    """Raised by minute-enforcing methods when the student is out of minutes.

    Carries the bilingual ``info`` payload from ``limit_service`` so callers
    can surface a friendly message without re-deriving it.
    """

    def __init__(self, info: dict):
        self.info = info
        super().__init__(info.get("reason", "daily_minutes_exhausted"))


class AccountPendingApproval(Exception):
    """Raised when a not-yet-approved student attempts an AI call.

    The provider is NOT called and no daily minutes are consumed; a
    ``cancelled`` usage row (cost 0) is logged for the denied attempt.
    """

    def __init__(self, info: dict | None = None):
        self.info = info or {
            "reason": "account_pending_approval",
            "message": {
                "ar": "حسابك بانتظار موافقة الإدارة. ستتمكن من استخدام المعلّم الذكي بعد الموافقة.",
                "en": "Your account is waiting for admin approval. AI features unlock after approval.",
            },
        }
        super().__init__("account_pending_approval")


def _enforce_student_approval(ctx) -> None:
    """Block AI for a not-yet-approved student BEFORE any provider call.

    No-op for anonymous/None users and for staff/teacher/admin (they are
    never gated). Logs a ``cancelled`` row (cost 0) for the denied attempt.
    """
    if not getattr(settings, "ONLENCO_STUDENT_APPROVAL_REQUIRED", True):
        return
    user = getattr(ctx, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return
    profile = getattr(user, "profile", None)
    if profile is None:
        return
    try:
        blocked = bool(profile.needs_admin_approval)
    except Exception:
        blocked = False
    if not blocked:
        return
    if _tracking_enabled():
        md = dict(ctx.metadata or {})
        md["blocked_reason"] = "account_pending_approval"
        ctx.metadata = md
        usage_logger.log_ai_usage(
            status=C.STATUS_CANCELLED, estimated_cost_usd=Decimal("0"),
            **ctx.log_kwargs(),
        )
    raise AccountPendingApproval()


@dataclass
class AICallContext:
    """Everything the wrapper needs to attribute a call. All optional."""
    user: object = None
    role: str | None = None
    feature: str = C.FEATURE_OTHER
    provider: str = C.PROVIDER_OPENAI
    model: str = ""
    session_id: str = ""
    lesson_id: int | None = None
    unit_id: int | None = None
    course_id: int | None = None
    organization: str = ""
    request_id: str | None = None
    metadata: dict = field(default_factory=dict)

    def log_kwargs(self) -> dict:
        return dict(
            user=self.user, role=self.role, feature=self.feature,
            provider=self.provider, model_name=self.model,
            session_id=self.session_id, lesson_id=self.lesson_id,
            unit_id=self.unit_id, course_id=self.course_id,
            organization=self.organization, request_id=self.request_id,
            metadata=self.metadata,
        )


def _tracking_enabled() -> bool:
    return bool(getattr(settings, "AI_USAGE_TRACKING_ENABLED", True))


def _api_base() -> str:
    return (getattr(settings, "AI_API_BASE", "") or "https://api.openai.com/v1").rstrip("/")


def _api_key() -> str:
    return getattr(settings, "AI_API_KEY", "") or ""


def _headers(json_body: bool = True) -> dict:
    h = {"Authorization": f"Bearer {_api_key()}"}
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _coerce_context(ctx, kwargs) -> AICallContext:
    if isinstance(ctx, AICallContext):
        return ctx
    return AICallContext(**{k: v for k, v in kwargs.items() if k in AICallContext.__dataclass_fields__})


def _extract_usage(data: dict) -> tuple[int, int]:
    usage = (data or {}).get("usage") or {}
    return (
        int(usage.get("prompt_tokens", 0) or 0),
        int(usage.get("completion_tokens", 0) or 0),
    )


def _enforce_minutes(ctx: AICallContext):
    """Block the call if a student speaking feature is out of daily minutes."""
    if ctx.feature not in C.MINUTE_BEARING_FEATURES:
        return
    user = ctx.user
    if user is None or not getattr(user, "is_authenticated", False):
        return
    if (ctx.role or "") in (C.ROLE_ADMIN, C.ROLE_TEACHER, C.ROLE_SYSTEM):
        return
    allowed, info = limit_service.check_can_start_ai_tutor(user)
    if not allowed:
        raise DailyMinutesExceeded(info)


# ---------------------------------------------------------------------------
# Chat / text
# ---------------------------------------------------------------------------

def chat(messages, *, context=None, enforce_minutes=False, timeout=25,
         extra_payload=None, **ctx_kwargs):
    """Non-streaming chat completion. Returns the raw provider JSON dict.

    Logs one success/failure ``AIUsageLog`` row. ``extra_payload`` merges into
    the request body (e.g. tools, temperature, response_format).
    """
    ctx = _coerce_context(context, ctx_kwargs)
    ctx.model = ctx.model or getattr(settings, "AI_MODEL", "gpt-4o-mini")
    _enforce_student_approval(ctx)
    if enforce_minutes:
        _enforce_minutes(ctx)

    if not _api_key():
        # No provider configured — log nothing-charged failure, signal caller.
        if _tracking_enabled():
            usage_logger.log_failure(error_message="ai_api_key_not_configured",
                                     **ctx.log_kwargs())
        raise RuntimeError("AI_API_KEY not configured")

    payload = {"model": ctx.model, "messages": messages}
    if extra_payload:
        payload.update(extra_payload)

    started = time.monotonic()
    try:
        resp = requests.post(
            f"{_api_base()}/chat/completions",
            headers=_headers(), json=payload, timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        latency_ms = int((time.monotonic() - started) * 1000)
        in_tok, out_tok = _extract_usage(data)
        if _tracking_enabled():
            usage_logger.log_success(
                input_tokens=in_tok, output_tokens=out_tok,
                latency_ms=latency_ms, **ctx.log_kwargs(),
            )
        return data
    except Exception as exc:
        latency_ms = int((time.monotonic() - started) * 1000)
        if _tracking_enabled():
            usage_logger.log_failure(
                error_message=_safe_error(exc), latency_ms=latency_ms,
                **ctx.log_kwargs(),
            )
        raise


def complete_text(prompt, *, system=None, context=None, **kwargs):
    """Convenience: single-prompt completion → returns the assistant text."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    data = chat(messages, context=context, **kwargs)
    try:
        return (data["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        return ""


def explain(prompt, *, context=None, **kwargs):
    """Alias for an explanation-style completion (library / vocabulary / lesson)."""
    return complete_text(prompt, context=context, **kwargs)


def generate_content(messages, *, context=None, **kwargs):
    """Teacher/admin/system content generation. Same path, role attribution
    is the caller's responsibility (pass role=...)."""
    return chat(messages, context=context, **kwargs)


def roleplay(messages, *, context=None, **kwargs):
    """Challenge roleplay turn — a chat completion tagged with the roleplay
    feature by the caller's context."""
    return chat(messages, context=context, **kwargs)


def generic_call(messages, *, context=None, **kwargs):
    """Escape hatch for any chat-shaped call not covered above."""
    return chat(messages, context=context, **kwargs)


# ---------------------------------------------------------------------------
# Streaming chat
# ---------------------------------------------------------------------------

def stream_chat(messages, *, context=None, enforce_minutes=False, timeout=(5, 30),
                extra_payload=None, **ctx_kwargs):
    """Generator yielding content deltas. Logs usage once the stream closes.

    Requests ``stream_options.include_usage`` so the trailing frame carries
    token counts; falls back to a 0-token success row if the provider omits it.
    A pre-first-byte failure logs a failed row.
    """
    ctx = _coerce_context(context, ctx_kwargs)
    ctx.model = ctx.model or getattr(settings, "AI_MODEL", "gpt-4o-mini")
    _enforce_student_approval(ctx)
    if enforce_minutes:
        _enforce_minutes(ctx)

    if not _api_key():
        if _tracking_enabled():
            usage_logger.log_failure(error_message="ai_api_key_not_configured",
                                     **ctx.log_kwargs())
        raise RuntimeError("AI_API_KEY not configured")

    payload = {
        "model": ctx.model, "messages": messages, "stream": True,
        "stream_options": {"include_usage": True},
    }
    if extra_payload:
        payload.update(extra_payload)

    started = time.monotonic()
    in_tok = out_tok = 0

    def _generate():
        nonlocal in_tok, out_tok
        import json as _json
        try:
            resp = requests.post(
                f"{_api_base()}/chat/completions",
                headers={**_headers(), "Accept": "text/event-stream"},
                json=payload, timeout=timeout, stream=True,
            )
            resp.raise_for_status()
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw:
                    continue
                line = raw.strip()
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    obj = _json.loads(chunk)
                except ValueError:
                    continue
                usage = obj.get("usage")
                if usage:
                    in_tok = int(usage.get("prompt_tokens", in_tok) or in_tok)
                    out_tok = int(usage.get("completion_tokens", out_tok) or out_tok)
                try:
                    delta = (obj["choices"][0].get("delta") or {}).get("content") or ""
                except (KeyError, IndexError, TypeError):
                    delta = ""
                if delta:
                    yield delta
            if _tracking_enabled():
                log_kwargs = ctx.log_kwargs()
                if in_tok == 0 and out_tok == 0:
                    # Provider closed the stream without a usage frame — record
                    # the call honestly rather than inventing token counts.
                    log_kwargs["metadata"] = {**(log_kwargs.get("metadata") or {}),
                                              "stream_usage_unavailable": True}
                usage_logger.log_success(
                    input_tokens=in_tok, output_tokens=out_tok,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    **log_kwargs,
                )
        except Exception as exc:
            if _tracking_enabled():
                usage_logger.log_failure(
                    error_message=_safe_error(exc),
                    latency_ms=int((time.monotonic() - started) * 1000),
                    **ctx.log_kwargs(),
                )
            raise

    return _generate()


# ---------------------------------------------------------------------------
# Audio — STT / TTS
# ---------------------------------------------------------------------------

def transcribe_audio(audio_bytes, *, filename="audio.webm", context=None,
                     response_format="verbose_json", timeout=(5, 15), **ctx_kwargs):
    """Speech-to-text. Returns provider JSON (incl. ``text`` and ``duration``).

    Audio duration (seconds) is read from the response and priced via the
    model's per-minute audio-input rate.
    """
    ctx = _coerce_context(context, ctx_kwargs)
    ctx.model = ctx.model or getattr(settings, "AI_STT_MODEL", "whisper-1")
    _enforce_student_approval(ctx)

    if not _api_key():
        if _tracking_enabled():
            usage_logger.log_failure(error_message="ai_api_key_not_configured",
                                     **ctx.log_kwargs())
        raise RuntimeError("AI_API_KEY not configured")

    started = time.monotonic()
    try:
        resp = requests.post(
            f"{_api_base()}/audio/transcriptions",
            headers=_headers(json_body=False),
            files={"file": (filename, audio_bytes)},
            data={"model": ctx.model, "response_format": response_format},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        duration = int(round(float(data.get("duration", 0) or 0)))
        if _tracking_enabled():
            usage_logger.log_success(
                audio_input_seconds=duration,
                latency_ms=int((time.monotonic() - started) * 1000),
                **ctx.log_kwargs(),
            )
        return data
    except Exception as exc:
        if _tracking_enabled():
            usage_logger.log_failure(
                error_message=_safe_error(exc),
                latency_ms=int((time.monotonic() - started) * 1000),
                **ctx.log_kwargs(),
            )
        raise


def synthesize_speech(text, *, voice="alloy", context=None, response_format="mp3",
                      timeout=30, **ctx_kwargs):
    """Text-to-speech. Returns raw audio bytes.

    No usage is returned by the endpoint; we estimate spoken seconds from the
    input length (~14 chars/sec) so the per-minute audio-output price applies.
    """
    ctx = _coerce_context(context, ctx_kwargs)
    ctx.model = ctx.model or getattr(settings, "AI_TTS_MODEL", "tts-1")
    _enforce_student_approval(ctx)

    if not _api_key():
        if _tracking_enabled():
            usage_logger.log_failure(error_message="ai_api_key_not_configured",
                                     **ctx.log_kwargs())
        raise RuntimeError("AI_API_KEY not configured")

    est_seconds = max(1, int(len(text or "") / 14)) if text else 0
    started = time.monotonic()
    try:
        resp = requests.post(
            f"{_api_base()}/audio/speech",
            headers=_headers(),
            json={"model": ctx.model, "voice": voice, "input": text or "",
                  "response_format": response_format},
            timeout=timeout,
        )
        resp.raise_for_status()
        if _tracking_enabled():
            usage_logger.log_success(
                audio_output_seconds=est_seconds,
                latency_ms=int((time.monotonic() - started) * 1000),
                **ctx.log_kwargs(),
            )
        return resp.content
    except Exception as exc:
        if _tracking_enabled():
            usage_logger.log_failure(
                error_message=_safe_error(exc),
                latency_ms=int((time.monotonic() - started) * 1000),
                **ctx.log_kwargs(),
            )
        raise


def generate_image(prompt, *, size="1024x1024", n=1, context=None,
                   response_format="b64_json", timeout=120, **ctx_kwargs):
    """Image generation. Returns the raw PNG bytes of the first image.

    Images carry no token usage; cost comes from ``AIModelPricing`` if a row
    exists for the model (per-image pricing is not modelled yet — see docs),
    otherwise 0 + a warning. Defaults to ``media_generation`` feature.
    """
    ctx = _coerce_context(context, ctx_kwargs)
    ctx.model = ctx.model or "gpt-image-1-mini"
    if ctx.feature == C.FEATURE_OTHER:
        ctx.feature = C.FEATURE_MEDIA_GENERATION

    if not _api_key():
        if _tracking_enabled():
            usage_logger.log_failure(error_message="ai_api_key_not_configured",
                                     **ctx.log_kwargs())
        raise RuntimeError("AI_API_KEY not configured")

    started = time.monotonic()
    try:
        resp = requests.post(
            f"{_api_base()}/images/generations",
            headers=_headers(),
            json={"model": ctx.model, "prompt": prompt, "n": n, "size": size},
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        import base64 as _b64
        png = _b64.b64decode(data["data"][0]["b64_json"])
        if _tracking_enabled():
            from . import cost_calculator
            img_cost = cost_calculator.calculate_image_cost(ctx.provider, ctx.model, n)
            md = dict(ctx.metadata or {})
            md["image_count"] = n
            ctx.metadata = md
            usage_logger.log_success(
                estimated_cost_usd=img_cost,
                latency_ms=int((time.monotonic() - started) * 1000),
                **ctx.log_kwargs(),
            )
        return png
    except Exception as exc:
        if _tracking_enabled():
            usage_logger.log_failure(
                error_message=_safe_error(exc),
                latency_ms=int((time.monotonic() - started) * 1000),
                **ctx.log_kwargs(),
            )
        raise


# ---------------------------------------------------------------------------
# Realtime (voice tutor) — usage is server-invisible; we log the session event
# ---------------------------------------------------------------------------

def log_realtime_session_start(*, context=None, **ctx_kwargs):
    """Record that a realtime AI-Tutor session was authorised.

    The realtime API bills browser↔OpenAI, so no tokens/cost are known here.
    Minutes are charged later via ``limit_service.finalize_ai_tutor_minutes``.
    This row marks the session start for the dashboard's request count.
    """
    ctx = _coerce_context(context, ctx_kwargs)
    ctx.model = ctx.model or getattr(settings, "AI_REALTIME_MODEL", "gpt-realtime")
    ctx.feature = C.FEATURE_AI_TUTOR
    if not _tracking_enabled():
        return None
    md = dict(ctx.metadata or {})
    md["event"] = "realtime_session_start"
    # Realtime token/cost is invisible server-side — flag for monthly
    # reconciliation against the provider invoice.
    md["realtime_reconcile_required"] = True
    ctx.metadata = md
    return usage_logger.log_success(**ctx.log_kwargs())


def _safe_error(exc: Exception) -> str:
    """Error string with any bearer token scrubbed out."""
    msg = str(exc)
    key = _api_key()
    if key and key in msg:
        msg = msg.replace(key, "***")
    return msg[:500]
