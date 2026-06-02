"""Optional LLM-driven motivation message generator.

Falls back to the template-bank generator (`message_generator`) whenever:
  - `AI_API_KEY` is empty
  - the API call fails / times out
  - the response is malformed

Output schema is identical to `message_generator.build_message`, so callers
get a `MotivationMessage` row regardless of path.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import requests
from django.conf import settings

from .. import constants as C
from ..models import (
    Achievement,
    LearnerActivitySnapshot,
    MotivationMessage,
)
from . import message_generator

logger = logging.getLogger(__name__)


def _build_prompt(*, lang: str, tone: str, snapshot: dict, context: str) -> tuple[str, str]:
    sys = (
        "You are an encouraging English-learning coach. "
        "Write ONE short motivation message (max 2 sentences) "
        f"in {'Arabic' if lang == 'ar' else 'English'}. "
        f"Use a {tone} tone. Reference at least one specific number from "
        "the student's snapshot if available. Reply ONLY with raw text, "
        "no JSON, no markdown."
    )
    user = (
        f"Context: {context}\n"
        f"Student snapshot: {json.dumps(snapshot, ensure_ascii=False)}"
    )
    return sys, user


def _call_llm(sys: str, user: str, *, user_obj=None) -> Optional[str]:
    if not settings.AI_API_KEY:
        return None
    # Routed through the centralised ai_usage wrapper (Prompt 12A): usage,
    # cost and failures are logged there — no inline metering here.
    try:
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        data = ai_client.chat(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": user},
            ],
            user=user_obj, feature=AC.FEATURE_MOTIVATION, model=settings.AI_MODEL,
            extra_payload={"max_tokens": 120, "temperature": 0.7}, timeout=20,
        )
        text = (data["choices"][0]["message"].get("content") or "").strip()
        return text or None
    except Exception as e:
        logger.warning("ai_message_generator: LLM call failed: %s", e)
        return None


def build_message_with_ai(
    user,
    *,
    message_type: str,
    snap: Optional[LearnerActivitySnapshot] = None,
    achievement: Optional[Achievement] = None,
    related_activity: str = "",
    extra: Optional[dict] = None,
) -> MotivationMessage:
    """Try the LLM; fall back to template banks on any failure."""
    extra = extra or {}
    lang = message_generator._user_language(user)
    tone = message_generator.select_tone(user, snap)

    snapshot_data: dict = {}
    if snap is not None:
        snapshot_data = {
            "lessons_today": snap.lessons_completed,
            "questions_today": snap.questions_answered,
            "accuracy": round(snap.quiz_accuracy or 0, 1),
            "streak_days": snap.current_streak_days,
            "ai_chat_minutes": snap.ai_chat_minutes,
            "words_read": snap.words_read,
        }

    context = message_type
    if achievement:
        context = f"achievement_unlocked:{achievement.code}"

    sys, prompt = _build_prompt(
        lang=lang, tone=tone, snapshot=snapshot_data, context=context
    )
    body = _call_llm(sys, prompt, user_obj=user)
    if not body:
        # Fallback to template path
        return message_generator.build_message(
            user,
            message_type=message_type,
            snap=snap,
            achievement=achievement,
            related_activity=related_activity,
            extra=extra,
        )

    title_map = {
        "ar": {
            C.MSG_ENCOURAGEMENT: "استمر",
            C.MSG_STREAK: "🔥 سلسلة!",
            C.MSG_COMEBACK: "نفتقدك",
            C.MSG_WEEKLY_SUMMARY: "ملخص أسبوعك",
        },
        "en": {
            C.MSG_ENCOURAGEMENT: "Keep going",
            C.MSG_STREAK: "🔥 Streak!",
            C.MSG_COMEBACK: "We miss you",
            C.MSG_WEEKLY_SUMMARY: "Your week",
        },
    }
    title = title_map.get(lang, title_map["en"]).get(
        message_type, "Keep going" if lang == "en" else "استمر"
    )

    msg = MotivationMessage.objects.create(
        user=user,
        message_type=message_type,
        title=title,
        message=body,
        language=lang,
        tone=tone,
        related_activity=related_activity,
        related_achievement=achievement,
        related_snapshot=snap,
        status=C.STATUS_GENERATED,
        sent_via=C.VIA_NONE,
        metadata={**extra, "source": "ai"},
    )
    return msg
