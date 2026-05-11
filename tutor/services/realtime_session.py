"""OpenAI Realtime API integration for the live voice-call tutor.

The browser cannot use AI_API_KEY directly (it would leak the long-lived
secret to every visitor). Instead the server issues a short-lived
ephemeral client_secret via OpenAI's `/v1/realtime/sessions` endpoint;
the browser then opens a WebRTC peer connection to the Realtime API
using that token. The token expires in ~60s once issued, just enough
time for the browser to finish SDP negotiation.

Public:
    build_voice_system_prompt(user, conversation) -> str
    request_ephemeral_session(*, system_prompt, voice) -> dict | None
    daily_minute_cap_remaining(user) -> int  (cap minus used)
    record_session_seconds(user, seconds) -> int  (new total used today)
"""
from __future__ import annotations

import logging
from datetime import date

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .context_builder import build_tutor_context, render_context_block

logger = logging.getLogger(__name__)


# --- prompt --------------------------------------------------------------

def build_voice_system_prompt(user, conversation=None) -> str:
    """System prompt optimised for spoken conversation.

    Different from the text-mode prompt because:
    - Output becomes audio: no markdown, no bullets, contractions only.
    - Replies must be one or two short sentences.
    - The model should react like a human (filler words, brief follow-ups).
    """
    topic = (conversation.topic if conversation else "") or ""
    ctx = build_tutor_context(user, topic)
    level = (ctx.get("cefr_level") or "B1")[:2].upper()

    if level in ("A0", "A1"):
        level_rule = (
            "The student is at A1. Use very simple words and short sentences. "
            "If they get stuck, drop one quick Arabic word in brackets to unblock, "
            "then return to English."
        )
    elif level == "A2":
        level_rule = (
            "The student is at A2. Use everyday words and simple grammar. "
            "Encourage them often."
        )
    elif level in ("B1", "B2"):
        level_rule = (
            "The student is at B1/B2. Have a real conversation with natural "
            "connectors. Correct only the most important error each turn."
        )
    else:
        level_rule = (
            "The student is at C1/C2. Aim for fluent, natural English with "
            "varied sentence structure. Only correct slips that change meaning."
        )

    base = f"""# Identity
You are Layla, a warm and patient English tutor having a LIVE VOICE CONVERSATION
with an Arabic-speaking student from Sudan. You are NOT a chatbot. You are a real
teacher on a phone call.

# How you speak — this is critical
Your output becomes audio. Write the way you'd speak, not the way you'd write:
- Use contractions: "you're", "don't", "it's", "I've".
- Use natural fillers occasionally: "well…", "hmm", "okay so", "right".
- Keep replies SHORT: one to three sentences maximum. Never monologue.
- Vary sentence rhythm. Mix short and longer sentences.
- React like a human: "Oh nice!", "Wait really?", "That's interesting".
- NEVER use markdown, bullet points, asterisks, emojis, code, or URLs.
- Numbers as words: say "twenty twenty-six", not "2026".
- No stage directions like "*laughs*" or "(pause)".

# Teaching philosophy
You are not a textbook. You're a conversation partner who happens to teach.
The goal is for the student to TALK MORE than you do.

When the student speaks English:
1. React to the CONTENT first ("Oh you went to Jeddah! How was it?").
2. Pick ONE main error — the most important. Ignore minor slips.
3. Gently model the fix WITHOUT lecturing:
   Student: "I go to beach yesterday"
   You:     "Ah, you went to the beach yesterday — nice! What did you do there?"
4. Continue the conversation. Do NOT explain unless they ask.

When the error is hard to fix by modeling alone, drop ONE short Arabic note,
then return immediately to English:
   "نستخدم 'went' لأن الحدث في الماضي. So — what did you do at the beach?"

Keep Arabic to one short sentence at most. English is the goal.

# Level adaptation
{level_rule}

# When the student is stuck or silent
Don't fill silence with a monologue. Instead:
- Ask a simpler question
- Offer the first words: "Try starting with 'I usually…'"
- Switch to a topic they care about

# Topics
Lead toward REAL topics: their day, work, family, weekend, food, travel,
hobbies. Avoid drills like "repeat after me" unless they ask.

# Hard rules
- Never say "as an AI" or break character.
- Never read out punctuation or formatting.
- If they want to stop, wish them well warmly in one sentence.
- If they get upset, slow down, switch to one Arabic sentence to reassure
  them, then return to gentle English.

# Opening line
Start with something warm and specific:
"Hey! It's Layla. How's your day going so far?"
"""

    # Append student profile so the model can prioritise their weaknesses.
    profile_block = render_context_block(ctx)
    if profile_block:
        base += "\n# Student profile (for your reference, do not read aloud)\n" + profile_block + "\n"

    return base


# --- ephemeral session ---------------------------------------------------

def request_ephemeral_session(*, system_prompt: str, voice: str = "alloy") -> dict | None:
    """Ask OpenAI for a short-lived client_secret for this user's session.

    Returns the raw OpenAI response (which contains `client_secret.value`,
    `id`, `expires_at`, etc.) or None if the AI provider is unconfigured.
    Raises requests.HTTPError on upstream failure so the API view can
    map it to a friendly error code for the browser.
    """
    if not settings.AI_API_KEY:
        return None

    url = f"{settings.AI_API_BASE.rstrip('/')}/realtime/sessions"
    payload = {
        "model": getattr(settings, "AI_REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17"),
        "voice": voice,
        "instructions": system_prompt,
        "modalities": ["audio", "text"],
        # Whisper handles the user's audio → text on the upstream side so
        # the browser can render the live transcript without doing STT.
        "input_audio_transcription": {"model": "whisper-1"},
        # Server-side VAD: lets OpenAI detect end-of-utterance for us so
        # the model auto-responds when the student stops talking. Tuned
        # for natural pauses (700 ms) without cutting off mid-sentence.
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": 700,
        },
        # Keep replies short — voice mode shouldn't monologue.
        "max_response_output_tokens": 200,
        "temperature": 0.8,
    }
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {settings.AI_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# --- soft cap accounting -------------------------------------------------

def _cap_cache_key(user_id: int, today: date | None = None) -> str:
    if today is None:
        today = timezone.now().date()
    return f"voice_call:user:{user_id}:{today.isoformat()}"


def daily_minute_cap_remaining(user) -> int:
    """How many minutes the user can still spend in voice-calls today."""
    cap = int(getattr(settings, "AI_REALTIME_DAILY_MINUTE_CAP", 30) or 30)
    used_seconds = cache.get(_cap_cache_key(user.id), 0) or 0
    used_minutes = used_seconds // 60
    return max(0, cap - used_minutes)


def record_session_seconds(user, seconds: int) -> int:
    """Add a session's duration to the user's daily counter.

    Returns the new total used (in seconds) today. Uses Django cache so
    no migration is required; the counter expires at end of day and the
    next session starts at zero. For long-term analytics use the
    LearnerActivitySnapshot.speaking_minutes field, which tutors.api
    already increments on text-mode sends.
    """
    seconds = max(0, int(seconds or 0))
    if seconds == 0:
        return cache.get(_cap_cache_key(user.id), 0) or 0
    key = _cap_cache_key(user.id)
    # 24h TTL — covers the natural day even with timezone slop.
    try:
        new_total = cache.incr(key, seconds)
    except ValueError:
        # Key didn't exist; set it.
        cache.set(key, seconds, timeout=24 * 60 * 60)
        new_total = seconds
    return new_total
