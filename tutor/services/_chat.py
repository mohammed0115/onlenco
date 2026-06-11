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
    # Correction style is per-band. A0/A1 cannot read jargon labels like
    # "Quick fix:" — for them, correction is just a gentle echo of the
    # right version. B1+ benefits from an explicit labelled line.
    if band == "A0":
        level_rule = (
            "1c. The student is at A0 — an absolute beginner. Speak as if to "
            "someone meeting English for the first time:\n"
            "  - Treat the session like an A0 World mission: one word, one "
            "picture or sound cue, one short sentence, speaking practice, "
            "then one simple question.\n"
            "  - Use English sentences of 3 to 5 words MAX. Never longer.\n"
            "  - No grammar theory, ever. No words like 'verb', 'tense', or "
            "'pronoun'. Teach by example, not by rule.\n"
            "  - Use Arabic for the tiny explanation when needed, then put "
            "the English target clearly after it.\n"
            "  - Ask exactly ONE simple personal question per turn "
            "(name, country, age, job, what you like).\n"
            "  - Always praise first ('Great!', 'Well done!') before asking "
            "anything else.\n"
            "  - When the student seems lost, give a one-word Arabic gloss in "
            "brackets and repeat the English target. Speak slowly — write "
            "naturally short, not crammed.\n"
            "  - NEVER speak technical tokens: no 'Quick fix:', no 'Error:', "
            "no JSON, no curly braces, no words like 'CEFR', 'level', "
            "'theta', 'metadata'. If you wouldn't say it to a child meeting "
            "English the first time, do not say it.\n"
        )
        correction_rule = (
            "2. GENTLE CORRECTION (A0 style): if they say something wrong, "
            "do NOT label it. No 'Quick fix:'. Just smile and repeat the "
            "right version naturally, as if echoing them. Example: they "
            "say \"I from Sudan\" → you reply \"Good! I am from Sudan.\" "
            "Then ask the next simple question.\n"
        )
    elif band == "A1":
        level_rule = (
            "1c. The student is at A1. Use very short simple English sentences "
            "(max 6-8 words). Avoid idioms and rare vocabulary. If they seem "
            "stuck, give a one-word Arabic translation in brackets to unblock "
            "them, then return to English.\n"
        )
        correction_rule = (
            "2. GENTLE CORRECTION (A1 style): repeat the correct sentence "
            "warmly without using a 'Quick fix:' label. Praise first.\n"
        )
    elif band == "A2":
        level_rule = (
            "1c. The student is at A2. Use simple present/past sentences and "
            "common everyday words. Encourage them with short praise.\n"
        )
        correction_rule = (
            "2. When the student makes a language error, gently correct it "
            "on a dedicated 'Quick fix:' line, then continue. Praise first.\n"
        )
    elif band in ("B1", "B2"):
        level_rule = (
            "1c. The student is at B1/B2. Have a real conversation. Use "
            "natural connectors ('however', 'because', 'although'). "
            "Correct grammar precisely on a Quick fix line; explain WHY in "
            "one short clause.\n"
        )
        correction_rule = (
            "2. When the student makes a language error, gently correct it "
            "on a dedicated 'Quick fix:' line and explain WHY in one short "
            "clause. Praise what they got right before correcting.\n"
        )
    else:  # C1, C2, anything richer
        level_rule = (
            "1c. The student is at C1/C2. Aim for fluent, professional "
            "vocabulary, varied syntax, and nuanced phrasing. Push register "
            "and idiomatic precision; only correct if the slip changes meaning.\n"
        )
        correction_rule = (
            "2. Correct only meaning-changing slips. When you do, mark it "
            "on a 'Quick fix:' line with a one-clause rationale.\n"
        )

    base = (
        "You are a friendly, focused AI English tutor for an adaptive learning "
        "platform called Onlenco. Follow these rules strictly:\n"
        "1. BE SHORT. 2-3 sentences max in text mode, 1-2 in voice mode. "
        "Long replies bore students; brevity is the rule.\n"
        "1b. Match the student's CEFR level — short sentences at A1/A2, "
        "slightly richer at B2/C1, but NEVER long.\n"
        + level_rule
        + correction_rule +
        "3. Prioritize the student's listed weaknesses when choosing examples.\n"
        "4. Always end with one short follow-up question. Ask only ONE "
        "question per reply — never two.\n"
    )
    # Rule 5 branches on language preference AND CEFR level. Arabic UI +
    # absolute-beginner level → Arabic-primary explanations. Anyone at A2
    # or higher gets English-primary even if their UI is Arabic — the
    # Arabic toggle is for the *interface*, not for the tutor's voice. A
    # B1 student who took the time to register for English coaching
    # shouldn't have their AI Tutor switch fully to Arabic just because
    # the dashboard is in Arabic. (Earlier all-Arabic behaviour was
    # disorienting at B1+ even when the user wrote a single English word
    # like "you" — the AI would reply 100% in Arabic, which broke the
    # immersion users explicitly come here for.)
    arabic_pref = (ctx or {}).get("language_preference") == "ar"
    arabic_primary = arabic_pref and band in ("A0", "A1")
    if arabic_primary:
        base += (
            "5. The student is a beginner with Arabic UI. Reply primarily in "
            "Arabic, but ALWAYS include the English target sentence/phrase the "
            "student should practise. Encourage them to repeat the English "
            "aloud.\n"
        )
    elif arabic_pref:
        base += (
            "5. The student's UI is Arabic but their level is "
            f"{band or 'B1'} — they can handle English. Reply PRIMARILY in "
            "English. Use Arabic only as a short bracketed gloss when a word "
            "would otherwise block comprehension. Even a one-word English "
            "input from the student deserves an English reply; ask for "
            "clarification in English, not Arabic.\n"
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

    # If the calling context names a curriculum-anchored tutor prompt,
    # append it so the model starts the conversation aligned with the
    # lesson the learner just opened. The prompts come from
    # `tutor.AITutorPrompt`, seeded by `import_a0_curriculum`.
    curriculum_seed = _curriculum_prompt_block(ctx)
    if curriculum_seed:
        base += curriculum_seed

    return base + "\nStudent profile context:\n" + render_context_block(ctx)


def _curriculum_prompt_block(ctx: dict) -> str:
    """Return a 'curriculum guidance' suffix when a lesson is in scope.

    Returns the empty string when there is no curriculum context — so
    free-form tutor chats (no lesson) keep their current behaviour.
    """
    if not ctx:
        return ""
    lesson_slug = ctx.get("lesson_slug")
    lesson_id = ctx.get("lesson_id")
    if not (lesson_slug or lesson_id):
        return ""
    try:
        from tutor.models import AITutorPrompt
    except Exception:
        return ""
    qs = AITutorPrompt.objects.filter(is_active=True).order_by("order")
    if lesson_id:
        qs = qs.filter(lesson_id=lesson_id)
    elif lesson_slug:
        qs = qs.filter(lesson_slug=lesson_slug)
    prompts = list(qs[:3])
    if not prompts:
        return ""
    lines = [
        "\nCurriculum guidance for this lesson — drive the first turns "
        "from these prompts:\n",
    ]
    for p in prompts:
        lines.append(
            f"  - Ask: {p.prompt_en!r}. Expected answer: "
            f"{p.expected_student_answer!r}. "
            f"Correction style: {p.correction_strategy}.\n"
        )
    return "".join(lines)


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
    # Plain, friendly fallback — no "Quick fix:" label or other
    # technical token, since this reply can land in an A0 chat.
    return (
        f"Thanks! You said: {user_message}\n\n"
        "What would you like to practise next?"
    )


def _over_limit_reply() -> str:
    return (
        "You've reached your AI tutor daily limit. "
        "Take a short break and review your recent practice.\n\n"
        "Want to try again tomorrow?"
    )


def _within_ai_tutor_limit(user, *, voice: bool) -> bool:
    """Daily-limit gate, routed through the single usage facade (Prompt 17.2B).

    ``tutor.services.usage_limits`` is the official AI-Tutor entry point — we no
    longer consult ``core.services.ai_usage.is_within_limit`` here. A text
    message is non-minute-bearing by default, so it only blocks when a voice
    message (or, if configured, a text message) is actually out of seconds.
    """
    try:
        from tutor.services import usage_limits
        mode = (
            usage_limits.MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE if voice
            else usage_limits.MODE_REGULAR_AI_TUTOR_MESSAGE
        )
        return usage_limits.can_start_ai_tutor_usage(user, mode)
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
    if not _within_ai_tutor_limit(user, voice=voice):
        logger.info("Tutor: user %s over daily AI limit", getattr(user, "id", None))
        return _over_limit_reply()

    payload = _build_payload(conversation, user_message, voice=voice, stream=False)

    try:
        # Routed through the centralised ai_usage wrapper (Prompt 12A.1):
        # the wrapper meters tokens/cost and logs success/failure once.
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        data = ai_client.chat(
            payload["messages"], user=user, feature=AC.FEATURE_AI_TUTOR,
            model=settings.AI_MODEL,
            extra_payload={"max_tokens": payload["max_tokens"]}, timeout=25,
        )
        content = data["choices"][0]["message"].get("content") or ""
        fire_post_chat_hooks(user, user_message)
        # Sanitise the AI's reply BEFORE returning. Even with the system
        # prompt's "no technical tokens" rule, models occasionally emit
        # field names like `cefr_level` or `user_answer`. This pass
        # converts them to the friendly equivalents. `display` mode
        # preserves punctuation; the TTS path runs `humanize_for_speech`
        # separately on the speech_text field at the API layer.
        try:
            # Centralised tutor-output sanitiser (Prompt 17.5) — wraps the
            # humaniser and applies a level-aware fallback, so text and voice
            # replies are cleaned through one door.
            from tutor.services.prompt_builder import sanitize_tutor_output_text
            user_lang = (
                "ar" if getattr(getattr(user, "profile", None),
                                "preferred_language", "en") == "ar"
                else "en"
            )
            level = getattr(getattr(user, "profile", None), "cefr_level", None)
            cleaned = sanitize_tutor_output_text(
                content.strip(), level=level, language=user_lang)
        except Exception:
            cleaned = content.strip()
        return cleaned or "Could you say a bit more? What do you mean?"
    except Exception as e:
        logger.exception("Tutor chat call failed: %s", e)
        fire_post_chat_hooks(user, user_message)
        return (
            "Thanks! I had a little trouble just now — could you "
            "say that again, maybe in another way?"
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
    if not _within_ai_tutor_limit(user, voice=voice):
        logger.info("Tutor stream: user %s over daily AI limit",
                    getattr(user, "id", None))
        yield _over_limit_reply()
        return

    payload = _build_payload(conversation, user_message, voice=voice, stream=True)

    try:
        # Routed through the centralised ai_usage wrapper (Prompt 12A.1):
        # the wrapper parses the SSE stream, captures the trailing usage
        # frame (or notes it missing), and logs success/failure once.
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        any_yielded = False
        for delta in ai_client.stream_chat(
            payload["messages"], user=user, feature=AC.FEATURE_AI_TUTOR,
            model=settings.AI_MODEL,
            extra_payload={"max_tokens": payload["max_tokens"]}, timeout=(5, 30),
        ):
            if delta:
                any_yielded = True
                yield delta
        if not any_yielded:
            # Stream opened but yielded nothing — surface a fallback so
            # the bubble isn't empty.
            yield "Could you say a bit more? What do you mean?"
        fire_post_chat_hooks(user, user_message)
    except Exception as e:
        logger.exception("Tutor chat_stream call failed: %s", e)
        fire_post_chat_hooks(user, user_message)
        yield (
            "(stub: AI temporarily unavailable) Thanks! "
            "Quick fix: Check your verb tense.\n\n"
            "Question: Can you rephrase that in a different way?"
        )
