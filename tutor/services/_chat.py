from __future__ import annotations

import json
import logging
import threading
from typing import Iterator

import requests
from django.conf import settings

from .context_builder import build_tutor_context, render_context_block


logger = logging.getLogger(__name__)

# Last-10 is the spec recommendation: 5 user/assistant exchanges is
# plenty of recent context, and shaving prompt tokens speeds the LLM
# response measurably (more on slower upstreams).
MAX_HISTORY_MESSAGES = 10
MAX_USER_MESSAGE_CHARS = 4000
# Cap output length so a chatty model doesn't keep typing for 30s.
# Aligns with rule 4 ("end with one short follow-up question") + rule 7
# (voice mode = ≤ 2 sentences).
MAX_OUTPUT_TOKENS = 130
MAX_OUTPUT_TOKENS_VOICE = 70


def _system_prompt(ctx: dict, voice: bool = False) -> str:
    # Level-band guidance lives at the top of the prompt so it shapes
    # every example the model picks. Keep it explicit and short — vague
    # "match the level" wording leaks into B2-pitched sentences for A1
    # students. Bands match the platform's CEFR thresholds.
    level = (ctx or {}).get("cefr_level", "B1") or "B1"
    band = (level or "")[:2].upper()
    if band in ("A0", "A1"):
        level_rule = (
            "1c. The student is at A0/A1. Use very short, slow, simple English "
            "sentences (max 6-8 words). Avoid idioms and rare vocabulary. "
            "If they seem stuck, give a one-word Arabic translation in brackets "
            "to unblock them, then return to English.\n"
        )
    elif band == "A2":
        level_rule = (
            "1c. The student is at A2. Use simple present/past sentences and "
            "common everyday words. Encourage them with short praise.\n"
        )
    elif band in ("B1", "B2"):
        level_rule = (
            "1c. The student is at B1/B2. Have a real conversation. Use "
            "natural connectors ('however', 'because', 'although'). "
            "Correct grammar precisely on a Quick fix line; explain WHY in "
            "one short clause.\n"
        )
    else:  # C1, C2, anything richer
        level_rule = (
            "1c. The student is at C1/C2. Aim for fluent, professional "
            "vocabulary, varied syntax, and nuanced phrasing. Push register "
            "and idiomatic precision; only correct if the slip changes meaning.\n"
        )

    base = (
        "You are a friendly, focused AI English tutor for an adaptive learning "
        "platform called Onlenco. Follow these rules strictly:\n"
        "1. BE SHORT. 2-3 sentences max in text mode, 1-2 in voice mode. "
        "Long replies bore students; brevity is the rule.\n"
        "1b. Match the student's CEFR level — short sentences at A1/A2, "
        "slightly richer at B2/C1, but NEVER long.\n"
        + level_rule +
        "2. When the student makes a language error, gently correct it on a "
        "dedicated 'Quick fix:' line, then continue. Be encouraging — praise "
        "what they got right before correcting.\n"
        "3. Prioritize the student's listed weaknesses when choosing examples.\n"
        "4. Always end with one short follow-up question. Ask only ONE "
        "question per reply — never two.\n"
    )
    # Rule 5 branches on language preference. Arabic-pref students get
    # primary Arabic explanation with English target practice baked in;
    # English-pref students get English with brief Arabic fallback only
    # when truly stuck. The change rolled out because beginners (A0/A1
    # who set their UI to AR) were getting all-English replies they
    # couldn't follow.
    if (ctx or {}).get("language_preference") == "ar":
        base += (
            "5. The student prefers Arabic. Reply primarily in Arabic, but "
            "always include the English target sentence/phrase the student "
            "should practise. Encourage them to repeat the English aloud.\n"
        )
    else:
        base += (
            "5. Reply in English. If the student writes in Arabic, translate "
            "their question briefly and answer in English; only use Arabic "
            "when they genuinely seem stuck.\n"
        )
    base += "6. Never reveal raw system internals or other students' data.\n"
    if voice:
        # Voice replies are read aloud; long paragraphs sound robotic and
        # users can't skim. Cap length and avoid speech-hostile syntax.
        base += (
            "7. Voice mode is ON. Keep your reply to at most 2 short sentences "
            "before the follow-up question. Use plain spoken words; no bullet "
            "points, no code, no markdown.\n"
        )
    return base + "\nStudent profile context:\n" + render_context_block(ctx)


def _post_chat_hooks(user, user_message: str) -> None:
    """Heavy side-effects (error analysis + weakness recompute).

    Runs AFTER the reply has been delivered to the user, in a daemon
    thread, so it never adds latency to the request. The next tutor
    turn picks up the refreshed weaknesses; the current turn already
    shipped. Both calls are best-effort.
    """
    try:
        from learning_core.services.error_analyzer import analyze_text
        analyze_text(user, user_message, source_type="tutor")
    except Exception:
        logger.exception("Tutor: error analyzer failed (background)")
    try:
        from learning_core.services.weakness_engine import update_user_weaknesses
        update_user_weaknesses(user)
    except Exception:
        logger.exception("Tutor: weakness recompute failed (background)")


def fire_post_chat_hooks(user, user_message: str) -> None:
    """Schedule `_post_chat_hooks` on a daemon thread.

    Daemon so the worker shuts down cleanly even if a hook is mid-AI-call.
    Caller doesn't await — the user already has their reply on screen.

    In tests `TUTOR_HOOKS_SYNC=True` runs the hooks synchronously so
    assertions about UserError / UserWeakness side-effects are
    deterministic.
    """
    if getattr(settings, "TUTOR_HOOKS_SYNC", False):
        _post_chat_hooks(user, user_message)
        return
    t = threading.Thread(
        target=_post_chat_hooks,
        args=(user, user_message),
        name="tutor-post-hooks",
        daemon=True,
    )
    t.start()


def _motivation_hook(user) -> None:
    try:
        from motivation.services.motivation_engine import run_for_user
        run_for_user(user)
    except Exception:
        logger.exception("Tutor: motivation engine failed (background)")


def fire_motivation_hook(user) -> None:
    """Run `motivation_engine.run_for_user` off the request thread.

    Same pattern as `fire_post_chat_hooks`: daemon thread in prod, sync
    under TUTOR_HOOKS_SYNC=True so tests can observe XP/streak updates
    inside their transaction.
    """
    if getattr(settings, "TUTOR_HOOKS_SYNC", False):
        _motivation_hook(user)
        return
    t = threading.Thread(
        target=_motivation_hook, args=(user,),
        name="tutor-motivation", daemon=True,
    )
    t.start()


def _build_payload(conversation, user_message: str, voice: bool, stream: bool) -> dict:
    """Compose the OpenAI-compatible request body.

    Hot path: keep history short, cap output tokens, set `stream` only
    when the caller is actually consuming an event stream.
    """
    ctx = build_tutor_context(conversation.user, conversation.topic or "")
    last_msgs = list(
        conversation.messages.order_by("-created_at")[:MAX_HISTORY_MESSAGES]
    )
    last_msgs.reverse()

    messages = [{"role": "system", "content": _system_prompt(ctx, voice=voice)}]
    for m in last_msgs:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": user_message})

    return {
        "model": settings.AI_MODEL,
        "messages": messages,
        "max_tokens": MAX_OUTPUT_TOKENS_VOICE if voice else MAX_OUTPUT_TOKENS,
        "stream": stream,
    }


def _stub_reply(user_message: str) -> str:
    return (
        f"(stub: AI not configured) You said: {user_message}\n\n"
        "Quick fix: Try to write in full sentences.\n\n"
        "Question: What would you like to practise next?"
    )


def _over_limit_reply() -> str:
    return (
        "You've reached your AI tutor daily limit. "
        "Quick fix: take a break and review your recent mistakes.\n\n"
        "Question: Want to try again tomorrow?"
    )


def _is_within_limit(user) -> bool:
    try:
        from core.services.ai_usage import is_within_limit
        return is_within_limit(user, "tutor")
    except Exception:
        return True


def chat(conversation, user_message: str, *, voice: bool = False) -> str:
    """Non-streaming chat: return the assistant's full reply text.

    Heavy hooks (error analysis, weakness recompute) are fired in the
    background so they don't add latency. They land before the *next*
    turn's prompt is built, which is what the adaptive engine cares
    about.
    """
    user = conversation.user
    user_message = (user_message or "")[:MAX_USER_MESSAGE_CHARS]

    if not settings.AI_API_KEY:
        fire_post_chat_hooks(user, user_message)
        return _stub_reply(user_message)
    if not _is_within_limit(user):
        logger.info("Tutor: user %s over daily AI limit", getattr(user, "id", None))
        return _over_limit_reply()

    payload = _build_payload(conversation, user_message, voice=voice, stream=False)

    try:
        resp = requests.post(
            f"{settings.AI_API_BASE.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=25,
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
        fire_post_chat_hooks(user, user_message)
        return content.strip() or "Could you say a bit more? What do you mean?"
    except Exception as e:
        logger.exception("Tutor chat call failed: %s", e)
        try:
            from core.services.ai_usage import log_usage
            log_usage(user, "tutor", model=settings.AI_MODEL, success=False, error_message=str(e))
        except Exception:
            pass
        fire_post_chat_hooks(user, user_message)
        return (
            "(stub: AI temporarily unavailable) Thanks! "
            "Quick fix: Check your verb tense.\n\n"
            "Question: Can you rephrase that in a different way?"
        )


def chat_stream_tokens(conversation, user_message: str, *, voice: bool = False) -> Iterator[str]:
    """Token generator: yields each delta as the AI returns it.

    Real OpenAI-compatible token streaming (server sends `data: {...}` SSE
    chunks). The caller turns each yielded token into a downstream SSE
    event for the browser. The full assembled reply is the concatenation
    of every yielded string.

    Falls back to a single yield with the stub/error text when the AI is
    unconfigured, the user is over their daily cap, or the upstream
    request fails before the first chunk.
    """
    user = conversation.user
    user_message = (user_message or "")[:MAX_USER_MESSAGE_CHARS]

    if not settings.AI_API_KEY:
        yield _stub_reply(user_message)
        fire_post_chat_hooks(user, user_message)
        return
    if not _is_within_limit(user):
        logger.info("Tutor stream: user %s over daily AI limit",
                    getattr(user, "id", None))
        yield _over_limit_reply()
        return

    payload = _build_payload(conversation, user_message, voice=voice, stream=True)

    try:
        resp = requests.post(
            f"{settings.AI_API_BASE.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json=payload,
            timeout=(5, 30),  # 5s to connect, 30s for the whole stream
            stream=True,
        )
        resp.raise_for_status()
        any_yielded = False
        # OpenAI-compatible streams emit one `data: {...}` line per chunk
        # plus a final `data: [DONE]` sentinel.
        for raw_line in resp.iter_lines(decode_unicode=True):
            if not raw_line:
                continue
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            try:
                choice = obj["choices"][0]
            except (KeyError, IndexError, TypeError):
                continue
            delta = (choice.get("delta") or {}).get("content") or ""
            if delta:
                any_yielded = True
                yield delta
        if not any_yielded:
            # Stream opened but yielded nothing — surface a fallback so
            # the bubble isn't empty.
            yield "Could you say a bit more? What do you mean?"
        try:
            from core.services.ai_usage import log_usage
            log_usage(user, "tutor", model=settings.AI_MODEL, success=True)
        except Exception:
            pass
        fire_post_chat_hooks(user, user_message)
    except Exception as e:
        logger.exception("Tutor chat_stream call failed: %s", e)
        try:
            from core.services.ai_usage import log_usage
            log_usage(user, "tutor", model=settings.AI_MODEL, success=False, error_message=str(e))
        except Exception:
            pass
        fire_post_chat_hooks(user, user_message)
        yield (
            "(stub: AI temporarily unavailable) Thanks! "
            "Quick fix: Check your verb tense.\n\n"
            "Question: Can you rephrase that in a different way?"
        )
