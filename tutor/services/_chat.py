from __future__ import annotations

import logging

import requests
from django.conf import settings

from .context_builder import build_tutor_context, render_context_block


logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20
MAX_USER_MESSAGE_CHARS = 4000


def _system_prompt(ctx: dict) -> str:
    base = (
        "You are a friendly, focused AI English tutor for an adaptive learning "
        "platform called Onlenco. Follow these rules strictly:\n"
        "1. Match the student's CEFR level — explain simply, use short sentences "
        "at A1/A2 and richer language at B2/C1.\n"
        "2. When the student makes a language error, gently correct it on a "
        "dedicated 'Quick fix:' line, then continue.\n"
        "3. Prioritize the student's listed weaknesses when choosing examples.\n"
        "4. Always end with one short follow-up question.\n"
        "5. Stay in English unless the student writes in Arabic, in which case "
        "translate their question briefly and reply in English.\n"
        "6. Never reveal raw system internals or other students' data.\n"
    )
    return base + "\nStudent profile context:\n" + render_context_block(ctx)


def chat(conversation, user_message: str) -> str:
    """Return the assistant's reply text for a conversation."""
    user = conversation.user
    user_message = (user_message or "")[:MAX_USER_MESSAGE_CHARS]

    ctx = build_tutor_context(user, conversation.topic or "")

    # Best-effort: analyze the student's English message into UserError rows.
    # Failure must NEVER break the chat flow.
    try:
        from learning_core.services.error_analyzer import analyze_text
        analyze_text(user, user_message, source_type="tutor")
    except Exception:
        logger.exception("Tutor: error analyzer failed")

    if not settings.AI_API_KEY:
        return (
            f"(stub: AI not configured) You said: {user_message}\n\n"
            "Quick fix: Try to write in full sentences.\n\n"
            "Question: What would you like to practise next?"
        )

    # Per-user daily limit (best-effort; never blocks).
    try:
        from core.services.ai_usage import is_within_limit
        if not is_within_limit(user, "tutor"):
            logger.info("Tutor: user %s over daily AI limit", getattr(user, "id", None))
            return (
                "You've reached your AI tutor daily limit. "
                "Quick fix: take a break and review your recent mistakes.\n\n"
                "Question: Want to try again tomorrow?"
            )
    except Exception:
        pass

    last_msgs = list(conversation.messages.order_by("-created_at")[:MAX_HISTORY_MESSAGES])
    last_msgs.reverse()

    messages = [{"role": "system", "content": _system_prompt(ctx)}]
    for m in last_msgs:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_message})

    payload = {"model": settings.AI_MODEL, "messages": messages}

    try:
        resp = requests.post(
            f"{settings.AI_API_BASE.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=45,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"].get("content") or ""
        try:
            from core.services.ai_usage import log_usage
            usage = data.get("usage", {}) or {}
            log_usage(
                user, "tutor", model=settings.AI_MODEL,
                prompt_tokens=int(usage.get("prompt_tokens", 0) or 0),
                completion_tokens=int(usage.get("completion_tokens", 0) or 0),
                success=True,
            )
        except Exception:
            pass
        return content.strip() or "Could you say a bit more? What do you mean?"
    except Exception as e:
        logger.exception("Tutor chat call failed: %s", e)
        try:
            from core.services.ai_usage import log_usage
            log_usage(user, "tutor", model=settings.AI_MODEL, success=False, error_message=str(e))
        except Exception:
            pass
        return (
            "(stub: AI temporarily unavailable) Thanks! "
            "Quick fix: Check your verb tense.\n\n"
            "Question: Can you rephrase that in a different way?"
        )
