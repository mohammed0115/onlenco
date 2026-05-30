"""Phase 7 — AI Tutor entry points used by Challenge endpoints.

Every function has the SAME shape:
  * Build context via `challenge_ai_context`.
  * Guard the call via `ai_usage_guard.can_call_challenge_ai`.
  * If allowed, invoke the LLM (via the existing chat layer when present)
    with a strict short prompt.
  * If anything fails, fall back to `challenge_rule_fallbacks`.
  * Persist a `ChallengeAIInteraction` row capturing what happened.
  * Return a small dict the view can render.

The LLM call is a SINGLE shot — no streaming, no tool use, no follow-up
rounds — because the surface is "one short helpful note" by design.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from django.conf import settings

from . import (
    ai_usage_guard, challenge_ai_context, challenge_rule_fallbacks,
)


logger = logging.getLogger(__name__)


# How many seconds we wait for the LLM. Kept tight — beyond this the
# student is better served by the fallback than a hanging spinner.
LLM_TIMEOUT_SECONDS = getattr(settings, "CHALLENGE_AI_TIMEOUT_SECONDS", 12)
LLM_MAX_TOKENS      = getattr(settings, "CHALLENGE_AI_MAX_TOKENS", 220)


# ---------------------------------------------------------------------------
# LLM client wrapper — defers to the existing tutor chat layer when
# available, otherwise calls the OpenAI-compatible endpoint directly.
# ---------------------------------------------------------------------------

def _call_llm(system_prompt: str, user_prompt: str) -> tuple[str, dict]:
    """Returns (text, telemetry). Raises on hard failure."""
    import json
    import urllib.request

    base = (getattr(settings, "AI_API_BASE", "") or "https://api.openai.com/v1").rstrip("/")
    key = getattr(settings, "AI_API_KEY", "") or ""
    if not key:
        raise RuntimeError("ai_no_api_key")

    model = getattr(settings, "TUTOR_TEXT_MODEL", "gpt-4o-mini")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "max_tokens":  LLM_MAX_TOKENS,
        "temperature": 0.4,
    }

    started = time.time()
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type":  "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=LLM_TIMEOUT_SECONDS) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    choices = (data.get("choices") or [])
    if not choices:
        raise RuntimeError("ai_empty_response")
    text = (choices[0].get("message") or {}).get("content") or ""
    telemetry = {
        "tokens_used": (data.get("usage") or {}).get("total_tokens"),
        "latency_ms":  int((time.time() - started) * 1000),
    }
    return text.strip(), telemetry


def _post_process(text: str) -> str:
    """Trim, drop anything resembling a JSON / underscore burst."""
    text = (text or "").strip()
    # Drop leading code fences.
    if text.startswith("```"):
        text = text.strip("`").strip()
    # Strip lone underscores so screen readers don't say "under-score".
    text = text.replace("_", " ")
    return text


# ---------------------------------------------------------------------------
# Use-case API.
# ---------------------------------------------------------------------------

def _dispatch(
    *,
    user, session, question, answer,
    interaction_type: str,
    fallback_pair: tuple[str, str],
) -> dict:
    """Shared scaffold: guardrail → LLM → fallback → record. Returns
    `{en, ar, status, reason}`."""
    allowed, reason = ai_usage_guard.can_call_challenge_ai(
        user, session, interaction_type,
    )
    if not allowed:
        en, ar = fallback_pair
        ai_usage_guard.record_ai_call(
            user=user, session=session, question=question, answer=answer,
            interaction_type=interaction_type,
            status="fallback", error_code=reason,
            response_en=en, response_ar=ar,
        )
        return {"en": en, "ar": ar, "status": "fallback", "reason": reason}

    ctx = challenge_ai_context.build_question_context(
        user, session, question, answer=answer,
        interaction_type=interaction_type,
    )
    user_prompt = challenge_ai_context.render_user_prompt(ctx)
    prompt_hash = challenge_ai_context.hash_prompt(user_prompt)

    try:
        text, telemetry = _call_llm(
            challenge_ai_context.system_prompt(), user_prompt,
        )
        clean = _post_process(text)
        if not clean:
            raise RuntimeError("ai_empty_after_clean")
        # Split EN/AR if the model gave both — heuristic: AR line starts
        # with a non-ASCII letter.
        en, ar = _split_bilingual(clean, ctx)
        ai_usage_guard.record_ai_call(
            user=user, session=session, question=question, answer=answer,
            interaction_type=interaction_type,
            status="success",
            response_en=en, response_ar=ar,
            prompt_hash=prompt_hash,
            tokens_used=telemetry.get("tokens_used"),
            latency_ms=telemetry.get("latency_ms"),
        )
        return {"en": en, "ar": ar, "status": "success", "reason": "ok"}
    except Exception as e:
        logger.warning(
            "Challenge AI call failed (type=%s err=%s) — using fallback.",
            interaction_type, e.__class__.__name__,
        )
        en, ar = fallback_pair
        ai_usage_guard.record_ai_call(
            user=user, session=session, question=question, answer=answer,
            interaction_type=interaction_type,
            status="failed", error_code=e.__class__.__name__,
            response_en=en, response_ar=ar,
            prompt_hash=prompt_hash,
        )
        return {"en": en, "ar": ar, "status": "failed", "reason": "llm_error"}


def _split_bilingual(text: str, ctx: dict) -> tuple[str, str]:
    """Best-effort split: first line(s) = EN, rest = AR if it starts with
    non-ASCII. When AR wasn't requested we leave it blank."""
    if ctx.get("user_lang_pref") != "ar":
        return text, ""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    en_lines, ar_lines = [], []
    for ln in lines:
        first = ln[:1]
        if first and ord(first) > 127:   # Non-ASCII → treat as AR.
            ar_lines.append(ln)
        else:
            en_lines.append(ln)
    return " ".join(en_lines) or text, " ".join(ar_lines)


# ---------------------------------------------------------------------------
# Public API (one fn per use case).
# ---------------------------------------------------------------------------

def explain_wrong_answer(user, challenge_answer) -> dict:
    session = challenge_answer.session
    question = challenge_answer.question
    ctx_fallback = challenge_ai_context.build_question_context(
        user, session, question, answer=challenge_answer,
        interaction_type="wrong_answer_explanation",
    )
    return _dispatch(
        user=user, session=session, question=question, answer=challenge_answer,
        interaction_type="wrong_answer_explanation",
        fallback_pair=challenge_rule_fallbacks.wrong_answer_explanation(ctx_fallback),
    )


def generate_speaking_feedback(user, challenge_answer, *, transcript: str = "") -> dict:
    session = challenge_answer.session
    question = challenge_answer.question
    ctx_fallback = challenge_ai_context.build_question_context(
        user, session, question, answer=challenge_answer,
        interaction_type="speaking_feedback",
    )
    if transcript:
        ctx_fallback["user_answer"] = transcript
    return _dispatch(
        user=user, session=session, question=question, answer=challenge_answer,
        interaction_type="speaking_feedback",
        fallback_pair=challenge_rule_fallbacks.speaking_feedback(ctx_fallback),
    )


def generate_end_challenge_advice(user, session) -> dict:
    """End-of-challenge nudge. Never requires a specific question."""
    fallback = challenge_rule_fallbacks.end_advice(
        ctx={}, session=session,
    )
    allowed, reason = ai_usage_guard.can_call_challenge_ai(
        user, session, "end_advice",
    )
    if not allowed:
        ai_usage_guard.record_ai_call(
            user=user, session=session,
            interaction_type="end_advice",
            status="fallback", error_code=reason,
            response_en=fallback[0], response_ar=fallback[1],
        )
        return {"en": fallback[0], "ar": fallback[1], "status": "fallback", "reason": reason}
    # Build a tiny context.
    last_q = session.answers.order_by("-answered_at").first()
    if last_q is None:
        return {"en": fallback[0], "ar": fallback[1], "status": "fallback", "reason": "no_answers"}
    return _dispatch(
        user=user, session=session, question=last_q.question, answer=last_q,
        interaction_type="end_advice",
        fallback_pair=fallback,
    )


def generate_mistake_explanation(user, mistake) -> dict:
    """Used by the Review queue (Phase 7+). Persists into
    StudentMistake.explanation_en/ar on success."""
    session = None
    question = mistake.question
    answer = mistake.challenge_answer
    fallback = challenge_rule_fallbacks.mistake_explanation(mistake)
    result = _dispatch(
        user=user, session=session, question=question, answer=answer,
        interaction_type="mistake_explanation",
        fallback_pair=fallback,
    )
    # Mirror the result onto StudentMistake so the Review UI can read it.
    try:
        if result["en"]:
            mistake.explanation_en = result["en"][:2000]
            mistake.explanation_ar = result["ar"][:2000]
            mistake.save(update_fields=["explanation_en", "explanation_ar", "updated_at"])
    except Exception:
        logger.exception("Persisting mistake explanation failed (pk=%s)", mistake.pk)
    return result


# ---------------------------------------------------------------------------
# Short roleplay.
# ---------------------------------------------------------------------------

def start_short_roleplay(user, session, question) -> dict:
    """Open a fresh roleplay session bound to a question. Returns
    `{roleplay_id, opening_en, opening_ar, status, reason}`."""
    from tutor.models import AIShortRoleplayMessage, AIShortRoleplaySession
    roleplay = AIShortRoleplaySession.objects.create(
        user=user, challenge_session=session, question=question,
        max_turns=ai_usage_guard.CHALLENGE_AI_MAX_ROLEPLAY_TURNS,
    )
    fallback = challenge_rule_fallbacks.roleplay_opener(ctx={
        "question_text": getattr(question, "question_text", ""),
    })
    allowed, reason = ai_usage_guard.can_call_challenge_ai(
        user, session, "roleplay",
    )
    if not allowed:
        opening_en, opening_ar = fallback
        AIShortRoleplayMessage.objects.create(
            roleplay_session=roleplay, sender="ai", message=opening_en,
        )
        roleplay.turns_count = 1
        roleplay.save(update_fields=["turns_count"])
        ai_usage_guard.record_ai_call(
            user=user, session=session, question=question,
            interaction_type="roleplay",
            status="fallback", error_code=reason,
            response_en=opening_en, response_ar=opening_ar,
            metadata={"roleplay_id": roleplay.pk},
        )
        return {"roleplay_id": roleplay.pk, "opening_en": opening_en,
                "opening_ar": opening_ar, "status": "fallback", "reason": reason}

    # Live LLM open.
    ctx = challenge_ai_context.build_question_context(
        user, session, question, interaction_type="roleplay",
    )
    user_prompt = challenge_ai_context.render_user_prompt(ctx)
    try:
        text, telemetry = _call_llm(
            challenge_ai_context.system_prompt(), user_prompt,
        )
        clean = _post_process(text)
        if not clean:
            raise RuntimeError("ai_empty_after_clean")
        opening_en, opening_ar = _split_bilingual(clean, ctx)
        AIShortRoleplayMessage.objects.create(
            roleplay_session=roleplay, sender="ai", message=opening_en,
        )
        roleplay.turns_count = 1
        roleplay.save(update_fields=["turns_count"])
        ai_usage_guard.record_ai_call(
            user=user, session=session, question=question,
            interaction_type="roleplay",
            status="success",
            response_en=opening_en, response_ar=opening_ar,
            tokens_used=telemetry.get("tokens_used"),
            latency_ms=telemetry.get("latency_ms"),
            metadata={"roleplay_id": roleplay.pk},
        )
        return {"roleplay_id": roleplay.pk,
                "opening_en": opening_en, "opening_ar": opening_ar,
                "status": "success", "reason": "ok"}
    except Exception as e:
        logger.warning("Roleplay open failed (%s) — fallback.", e.__class__.__name__)
        opening_en, opening_ar = fallback
        AIShortRoleplayMessage.objects.create(
            roleplay_session=roleplay, sender="ai", message=opening_en,
        )
        roleplay.turns_count = 1
        roleplay.save(update_fields=["turns_count"])
        ai_usage_guard.record_ai_call(
            user=user, session=session, question=question,
            interaction_type="roleplay",
            status="failed", error_code=e.__class__.__name__,
            response_en=opening_en, response_ar=opening_ar,
            metadata={"roleplay_id": roleplay.pk},
        )
        return {"roleplay_id": roleplay.pk,
                "opening_en": opening_en, "opening_ar": opening_ar,
                "status": "failed", "reason": "llm_error"}


def continue_short_roleplay(user, roleplay_session, user_message: str) -> dict:
    """Continue an active roleplay. Returns
    `{reply_en, reply_ar, status, reason, turns_remaining}`."""
    from tutor.models import AIShortRoleplayMessage
    if roleplay_session.user_id != user.pk:
        return {"reply_en": "", "reply_ar": "",
                "status": "failed", "reason": "not_owner", "turns_remaining": 0}
    if roleplay_session.status != "active":
        return {"reply_en": "", "reply_ar": "",
                "status": "failed", "reason": "not_active", "turns_remaining": 0}
    if roleplay_session.turns_count >= roleplay_session.max_turns:
        roleplay_session.status = "completed"
        from django.utils import timezone
        roleplay_session.completed_at = timezone.now()
        roleplay_session.save(update_fields=["status", "completed_at"])
        return {"reply_en": "Great practice — that's enough for now. Try the next card!",
                "reply_ar": "تدريب ممتاز — يكفي الآن. جرّب البطاقة التالية!",
                "status": "completed", "reason": "max_turns",
                "turns_remaining": 0}

    AIShortRoleplayMessage.objects.create(
        roleplay_session=roleplay_session, sender="user",
        message=str(user_message or "")[:500],
    )
    # Reuse the explain-flow's dispatcher to keep the surface area small.
    session = roleplay_session.challenge_session
    question = roleplay_session.question
    fallback = (
        "Nice try! Let's try one more.",
        "محاولة جيدة! هيا نجرّب مرة أخرى.",
    )
    result = _dispatch(
        user=user, session=session, question=question, answer=None,
        interaction_type="roleplay",
        fallback_pair=fallback,
    )
    AIShortRoleplayMessage.objects.create(
        roleplay_session=roleplay_session, sender="ai",
        message=result["en"],
    )
    roleplay_session.turns_count += 1
    if roleplay_session.turns_count >= roleplay_session.max_turns:
        roleplay_session.status = "completed"
        from django.utils import timezone
        roleplay_session.completed_at = timezone.now()
        roleplay_session.save(update_fields=["turns_count", "status", "completed_at"])
    else:
        roleplay_session.save(update_fields=["turns_count"])
    return {
        "reply_en": result["en"], "reply_ar": result["ar"],
        "status":   result["status"], "reason": result["reason"],
        "turns_remaining": max(0, roleplay_session.max_turns - roleplay_session.turns_count),
    }
