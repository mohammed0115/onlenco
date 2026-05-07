from __future__ import annotations

import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


def _system_prompt(level: str, topic: str) -> str:
    topic_line = f"Topic: {topic}." if topic else ""
    return (
        "You are a friendly AI English tutor. "
        f"The student's CEFR level is {level}. "
        "Respond at or just slightly above their level. "
        "Always end with a short follow-up question. "
        "When the student makes a grammar error, gently correct it in a dedicated "
        "\"Quick fix:\" line, then continue the conversation. "
        "Stay in English unless the student writes in Arabic, in which case translate "
        "their question and answer in English. "
        f"{topic_line}"
    ).strip()


def chat(conversation, user_message: str) -> str:
    """Return the assistant's reply text for a conversation."""
    level = getattr(getattr(conversation.user, "profile", None), "cefr_level", None) or "B1"
    topic = conversation.topic or ""

    if not settings.AI_API_KEY:
        return (
            f"(stub: AI not configured) You said: {user_message}\n\n"
            "Quick fix: Try to write in full sentences.\n\n"
            "Question: What would you like to practise next?"
        )

    # System + last 20 messages + new user message
    last_msgs = list(conversation.messages.order_by("-created_at")[:20])
    last_msgs.reverse()

    messages = [{"role": "system", "content": _system_prompt(level, topic)}]
    for m in last_msgs:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": settings.AI_MODEL,
        "messages": messages,
    }

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
        return content.strip() or "Could you say a bit more? What do you mean?"
    except Exception as e:
        logger.exception("Tutor chat call failed: %s", e)
        return (
            "(stub: AI temporarily unavailable) Thanks! "
            "Quick fix: Check your verb tense.\n\n"
            "Question: Can you rephrase that in a different way?"
        )

