"""Central AI-Tutor prompt building, language policy, and output sanitisation
(Prompt 17.5).

This is the single place that decides:

    * the language policy for a CEFR level (how much Arabic support, how short),
    * how the tutor opens a call,
    * and — critically — how a reply is cleaned before it is shown or spoken,
      so the student never sees raw technical tokens (JSON, file names, provider
      / model names, underscores, UUIDs, debug text).

It does NOT re-implement the heavy sanitiser: ``core.services.text_humanizer``
already strips banned identifiers, snake_case, markdown, JSON and unspeakable
artifacts with a safe bilingual fallback. We delegate to it and add a
level-aware fallback on top. The detailed level/language rules already encoded
in ``_chat._system_prompt`` and ``realtime_session.build_voice_system_prompt``
stay the source of those prompts; this module is the unified entry point and
wraps them so every path (text / voice message / call) goes through one door.
"""
from __future__ import annotations

import re

# Mode constants mirror the usage facade so the whole tutor layer speaks one
# vocabulary. Imported lazily-safe: usage_limits never imports this module.
from tutor.services.usage_limits import (  # noqa: F401
    MODE_PLACEMENT_SPEAKING_CALL,
    MODE_REGULAR_AI_TUTOR_CALL,
    MODE_REGULAR_AI_TUTOR_MESSAGE,
    MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE,
)

_CALL_MODES = frozenset({MODE_REGULAR_AI_TUTOR_CALL, MODE_PLACEMENT_SPEAKING_CALL})

_SAFE_FALLBACK_AR = "حاول مرة أخرى بجملة قصيرة."
_SAFE_FALLBACK_EN = "Please try again with a short sentence."


def _band(level) -> str:
    return (str(level or "B1")[:2]).upper()


# ---------------------------------------------------------------------------
# Language policy
# ---------------------------------------------------------------------------
def should_use_arabic_support(level) -> bool:
    """Whether replies may lean on Arabic to explain (beginner levels)."""
    return _band(level) in ("A0", "A1", "A2")


def should_keep_reply_short(level) -> bool:
    """Whether replies must stay very short (beginner levels)."""
    return _band(level) in ("A0", "A1", "A2")


def get_language_policy(level) -> dict:
    """Resolved language policy for a CEFR level.

    ``reply_language``:
        ``ar_primary``       — A0/A1: reply mainly in Arabic, English target only.
        ``en_with_ar_gloss`` — A2: simple English with a short Arabic hint.
        ``en``               — B1+: mostly English, Arabic only on request.
    """
    band = _band(level)
    if band in ("A0", "A1"):
        reply_language = "ar_primary"
    elif band == "A2":
        reply_language = "en_with_ar_gloss"
    else:
        reply_language = "en"
    return {
        "level": str(level or "B1"),
        "band": band,
        "arabic_support": should_use_arabic_support(level),
        "keep_short": should_keep_reply_short(level),
        "reply_language": reply_language,
    }


# ---------------------------------------------------------------------------
# Sanitisation
# ---------------------------------------------------------------------------
def _safe_fallback(level=None, language=None) -> str:
    if (language == "ar") or should_use_arabic_support(level):
        return _SAFE_FALLBACK_AR
    return _SAFE_FALLBACK_EN


# Provider / model names that must never reach a learner.
_PROVIDER_RE = re.compile(
    r"\b(openai|anthropic|gpt-?4o(?:-mini)?|gpt-?\d*|whisper(?:-\d)?|"
    r"claude|gemini|llama|mistral|tts-1)\b",
    re.IGNORECASE,
)
_FILE_RE = re.compile(
    r"\b[\w./-]+\.(?:webm|mp4|m4v|json|py|html?|png|jpe?g|gif|wav|ogg|mp3|txt|js|css|md|csv|pdf)\b",
    re.IGNORECASE,
)
_UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE
)


def _strip_technical(s: str) -> str:
    """Remove code-like / data-like spans that ``humanize_text`` leaves intact
    in display mode (JSON, fenced code, file names, URLs, UUIDs, provider names,
    underscore runs, repeated punctuation)."""
    s = re.sub(r"```.*?```", " ", s, flags=re.S)              # fenced code
    s = re.sub(r"`[^`]*`", " ", s)                             # inline code
    s = re.sub(r"\{[^{}]*[:\"'][^{}]*\}", " ", s)             # JSON-ish objects
    s = re.sub(r"\[[^\[\]]*[:\"'][^\[\]]*\]", " ", s)         # JSON-ish arrays
    s = _FILE_RE.sub(" ", s)                                   # file names
    s = re.sub(r"\bhttps?://\S+", " ", s)                      # URLs
    s = _UUID_RE.sub(" ", s)                                   # UUIDs
    s = _PROVIDER_RE.sub(" ", s)                               # provider/model names
    s = re.sub(r"_{2,}", " ", s)                               # ___ runs
    s = re.sub(r"([!?.,/\\])\1{2,}", r"\1", s)                # repeated punctuation
    return s


def sanitize_tutor_output_text(text, level=None, language=None) -> str:
    """Clean a tutor reply before it is shown or spoken (Prompt 17.5 C/F).

    Delegates the heavy lifting to ``core.services.text_humanizer.humanize_text``
    (banned identifiers, snake_case → words, JSON / markdown / unspeakable
    artifacts) and applies a level-aware fallback if nothing intelligible is
    left. Never raises; always returns a non-empty string.
    """
    lang = "ar" if language == "ar" else "en"
    try:
        pre = _strip_technical(text or "")
        # Nothing intelligible survived stripping — skip the humaniser (it would
        # return its own generic fallback) and use our level-aware fallback.
        if not pre.strip():
            return _safe_fallback(level, language)
        from core.services.text_humanizer import humanize_text
        cleaned = (humanize_text(pre, language=lang, mode="display") or "").strip()
    except Exception:
        cleaned = (text or "").strip()
    if not cleaned:
        return _safe_fallback(level, language)
    return cleaned


def sanitize_tutor_input_context(context):
    """Scrub free-text fields in the internal context before they reach the
    prompt, so technical tokens captured from logs/errors never leak in."""
    if not isinstance(context, dict):
        return context
    try:
        from core.services.text_humanizer import humanize_text
    except Exception:
        return context
    out = dict(context)
    if isinstance(out.get("topic"), str):
        out["topic"] = humanize_text(out["topic"], mode="display")
    errs = out.get("recent_errors")
    if isinstance(errs, list):
        cleaned = []
        for e in errs:
            if isinstance(e, dict):
                e = dict(e)
                for key in ("original_text", "explanation", "text"):
                    if isinstance(e.get(key), str):
                        e[key] = humanize_text(e[key], mode="display")
            cleaned.append(e)
        out["recent_errors"] = cleaned
    return out


# ---------------------------------------------------------------------------
# Prompt + opening builders
# ---------------------------------------------------------------------------
def build_opening_instruction(student, mode, lesson_context=None) -> str:
    """How the tutor should OPEN a call (the model generates the real greeting).

    Only call modes have an opening; message modes return "". The phrasing
    keeps the "tutor speaks first" contract and adds a beginner clause for
    A0/A1. It is our own controlled copy — no technical tokens.
    """
    if mode not in _CALL_MODES:
        return ""
    level = getattr(getattr(student, "profile", None), "cefr_level", None) or "B1"
    if mode == MODE_PLACEMENT_SPEAKING_CALL:
        return (
            "Begin the placement test NOW. Do not wait for the student to "
            "speak first. Greet them in one short sentence, then immediately "
            "ask the first question from your list. Keep it slow and simple."
        )
    base = (
        "Begin NOW. Do not wait for the student to speak first. Greet them "
        "warmly in one short sentence and ask what they would like to "
        "practice today."
    )
    if should_use_arabic_support(level):
        base += (
            " The student is a beginner: use ONE very short, simple English "
            "sentence and you may add a short Arabic hint. No long sentences."
        )
    return base


def build_tutor_system_prompt(student, mode, lesson_context=None, skill=None) -> str:
    """Unified entry point for the tutor system prompt.

    Call modes delegate to the realtime voice prompt; message modes delegate to
    the chat prompt, with the internal context scrubbed first. The existing
    builders remain the source of the detailed level/language rules.
    """
    if mode in _CALL_MODES:
        from tutor.services.realtime_session import build_voice_system_prompt
        return build_voice_system_prompt(student, lesson_context)
    from tutor.services._chat import _system_prompt
    from tutor.services.context_builder import build_tutor_context
    topic = lesson_context if isinstance(lesson_context, str) else ""
    ctx = sanitize_tutor_input_context(build_tutor_context(student, topic))
    return _system_prompt(ctx, voice=(mode == MODE_REGULAR_AI_TUTOR_VOICE_MESSAGE))
