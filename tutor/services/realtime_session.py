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

import requests
from django.conf import settings

from subscriptions.services import preference_service

from .context_builder import build_tutor_context, render_context_block

logger = logging.getLogger(__name__)


def _avatar_first_name(avatar) -> str:
    """Pull the human first name from a `name_en` like 'Layla — Friendly Teacher'.
    Used to brand the tutor identity in the system prompt."""
    if avatar is None:
        return "Layla"
    raw = (getattr(avatar, "name_en", "") or "").strip()
    return raw.split("—", 1)[0].strip() or "Layla"


# --- prompt --------------------------------------------------------------

def _build_placement_voice_prompt(conversation, user) -> str:
    """Structured-interview prompt for placement Part 2.

    Looks up the linked PlacementAttempt via the reverse
    ``placement_attempts`` related-set on TutorConversation, pulls its
    5 ``section="speaking"`` questions (admin-curated, already
    pre-selected when the attempt was created), and writes them into
    the system prompt so the AI asks them in order rather than holding
    an open-ended chat.

    Returns "" when this conversation isn't linked to an active
    placement attempt — caller falls back to the generic prompt.
    """
    try:
        attempt = conversation.placement_attempts.filter(
            status__in=["written_completed", "speaking_completed", "started"],
        ).order_by("-id").first()
    except Exception:
        attempt = None
    if attempt is None:
        return ""

    speaking_qs = list(
        attempt.questions
        .filter(section="speaking")
        .select_related("question")
        .order_by("order", "id")[:5]
    )
    if not speaking_qs:
        return ""

    tutor_name = _avatar_first_name(preference_service.resolve_avatar_for(user))

    # Render the 5 questions as a numbered list the model will follow.
    # We use the English question text — the AI sees both languages
    # via the user's spoken response, but the question itself is asked
    # in English to assess English skill.
    question_lines = "\n".join(
        f"{i + 1}. {(aq.question.question_text or '').strip()}"
        for i, aq in enumerate(speaking_qs)
    )

    return f"""# Identity & role
You are {tutor_name}, conducting a SHORT PLACEMENT INTERVIEW with an
Arabic-speaking student from Sudan. This is NOT an open conversation —
it's a structured 5-question oral assessment used to place the student
at a CEFR level (A0 / A1 / A2 / B1 / B2 / C1 / C2).

# How you speak
Your output becomes audio. Speak like a teacher running an oral test:
- Warm but focused. Brief praise OK; no monologue.
- One question at a time. Wait for the student's full answer before
  moving to the next one.
- Use contractions: "you're", "don't", "it's".
- If they don't understand, repeat the question more slowly with
  simpler words. Do NOT translate to Arabic unless they look completely
  stuck after two attempts — then ONE short Arabic clarification.
- NEVER add follow-up questions of your own. Stick to the 5 below.
- NEVER use markdown, bullets, asterisks, emojis.

# The 5 questions — ask in this exact order, one at a time
{question_lines}

# Pacing rules
1. Open with: "Hi! I'm {tutor_name}. I'll ask you five quick questions
   to see your English level. Take your time. Ready? Here's the first one."
2. Ask question 1. Wait for the student's response (one to several
   sentences). Acknowledge briefly ("OK", "Got it", "Nice"). Move on.
3. Repeat for questions 2, 3, 4, 5.
4. After question 5 and the student's answer, say:
   "Great — that's all five questions. You did well. I'm sending you
   to your results now."
   Then stop talking. The system will end the call automatically.

# Hard rules
- Do NOT improvise extra questions, even if the student is fluent.
- Do NOT correct grammar in real time during the test — this is an
  assessment, not a lesson. The scorer reads the transcript afterward.
- Do NOT skip a question.
- Do NOT continue past question 5.
- If the student tries to chat freely, gently redirect: "Let's stay
  with the test for now — here's the next question."
- Never say "as an AI" or break character.

# Opening line
Start exactly with: "Hi! I'm {tutor_name}. I'll ask you five quick
questions to see your English level. Take your time. Ready? Here's
the first one."
"""


def build_voice_system_prompt(user, conversation=None) -> str:
    """System prompt optimised for spoken conversation.

    Different from the text-mode prompt because:
    - Output becomes audio: no markdown, no bullets, contractions only.
    - Replies must be one or two short sentences.
    - The model should react like a human (filler words, brief follow-ups).

    Special-case: when the conversation is tagged for a placement
    attempt, we deliver a STRUCTURED interview script instead of an
    open-ended chat. The AI walks the student through the 5
    pre-selected speaking questions in order, then signals end of test.
    """
    topic = (conversation.topic if conversation else "") or ""

    # Placement Part 2 — structured interview using admin-curated questions.
    if topic == "placement" and conversation is not None:
        placement_prompt = _build_placement_voice_prompt(conversation, user)
        if placement_prompt:
            return placement_prompt

    ctx = build_tutor_context(user, topic)
    level = (ctx.get("cefr_level") or "B1")[:2].upper()
    tutor_name = _avatar_first_name(preference_service.resolve_avatar_for(user))

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
You are {tutor_name}, a warm and patient English tutor having a LIVE VOICE CONVERSATION
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
"Hey! It's {tutor_name}. How's your day going so far?"
"""

    # Append student profile so the model can prioritise their weaknesses.
    profile_block = render_context_block(ctx)
    if profile_block:
        base += "\n# Student profile (for your reference, do not read aloud)\n" + profile_block + "\n"

    return base


# --- ephemeral session ---------------------------------------------------

# Voices supported by the OpenAI GA Realtime API as of the GA migration.
# The old Beta voices (``nova``, ``onyx``, ``fable``) still work for
# ``/v1/audio/speech`` (TTS-1) but were retired on the realtime endpoint
# and now return 400 ``invalid_value``. We map retired IDs to a sensible
# GA-era equivalent so users with old preferences don't get errors.
REALTIME_GA_VOICES = {
    "alloy", "ash", "ballad", "coral", "echo",
    "sage", "shimmer", "verse", "marin", "cedar",
}
RETIRED_VOICE_FALLBACKS = {
    "nova":  "shimmer",   # warm female → closest GA female
    "onyx":  "ash",       # deep male   → closest GA deep male
    "fable": "ballad",    # soft narrator → closest GA storyteller
}


def coerce_supported_voice(voice: str) -> str:
    """Normalise a stored voice ID to one the GA Realtime API accepts.

    Unknown / empty inputs degrade to ``alloy`` (the universal safe default).
    """
    v = (voice or "").strip().lower()
    if v in REALTIME_GA_VOICES:
        return v
    if v in RETIRED_VOICE_FALLBACKS:
        return RETIRED_VOICE_FALLBACKS[v]
    return "alloy"


def request_ephemeral_session(*, system_prompt: str, voice: str = "alloy") -> dict | None:
    """Ask OpenAI for a short-lived client_secret for this user's session.

    Uses the **GA Realtime API** at ``POST /v1/realtime/client_secrets``
    (the old Beta endpoint ``/v1/realtime/sessions`` returns 400 with
    ``beta_api_shape_disabled`` since the GA migration). Returns the
    upstream JSON, normalised so callers can keep reading
    ``session["client_secret"]["value"]`` / ``session["id"]`` regardless
    of which shape OpenAI returns.
    """
    if not settings.AI_API_KEY:
        return None

    voice = coerce_supported_voice(voice)
    url = f"{settings.AI_API_BASE.rstrip('/')}/realtime/client_secrets"
    payload = {
        "session": {
            "type": "realtime",
            "model": getattr(settings, "AI_REALTIME_MODEL", "gpt-realtime"),
            "instructions": system_prompt,
            "max_output_tokens": 200,
            "audio": {
                "output": {"voice": voice},
                "input": {
                    # Whisper handles the user's audio → text upstream so the
                    # browser can render the live transcript without local STT.
                    "transcription": {"model": "whisper-1"},
                    # Server-side VAD: OpenAI detects end-of-utterance for us
                    # so the model auto-responds when the student stops talking.
                    # Tuned for natural pauses (700 ms) without cutting mid-sentence.
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 700,
                    },
                },
            },
        }
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
    if not resp.ok:
        # Surface OpenAI's actual error body so production failures don't
        # collapse into an opaque 503 in our logs. (We were seeing 400s
        # whose root cause was invisible without this.)
        logger.error(
            "OpenAI realtime/client_secrets %s — voice=%s body=%s",
            resp.status_code, voice, resp.text[:800],
        )
    resp.raise_for_status()
    body = resp.json()
    # Normalise to the legacy shape callers expect:
    #   {"client_secret": {"value": "..."}, "id": "...", "expires_at": ...}
    session = body.get("session") or {}
    return {
        "client_secret": {"value": body.get("value") or ""},
        "id": session.get("id") or body.get("id") or "",
        "expires_at": body.get("expires_at") or session.get("expires_at"),
        "model": session.get("model") or "",
    }


# --- quota accounting (DB-backed via subscriptions.quota_service) --------
#
# Sprint 1 introduced SubscriptionPlan + UserDailyQuota; Sprint 2 adds
# FreeTrialUsage + AITutorSession. This module keeps its public surface
# unchanged so existing call-sites in tutor.api.views keep working, but
# the storage is now DB-backed and unified across subscription + trial.

def daily_minute_cap_remaining(user) -> int:
    """How many MINUTES the user can still spend in AI-Tutor today.

    Reads from subscription quota first, falls back to the one-shot
    trial. Returns 0 when both are exhausted (the caller blocks the
    session and shows the upgrade page).
    """
    try:
        from subscriptions.services.quota_service import effective_ai_tutor_remaining
    except Exception:
        return 0
    seconds, _source = effective_ai_tutor_remaining(user)
    return seconds // 60


def daily_seconds_remaining(user) -> int:
    """Same as ``daily_minute_cap_remaining`` but in seconds (more precise)."""
    try:
        from subscriptions.services.quota_service import effective_ai_tutor_remaining
    except Exception:
        return 0
    seconds, _source = effective_ai_tutor_remaining(user)
    return seconds


def record_session_seconds(user, seconds: int) -> int:
    """Charge ``seconds`` to the user's bucket. Returns NEW used-total today.

    Legacy shim: existing tutor.api.views call this on voice-call hang-up.
    New code should use ``subscriptions.services.session_service.end_session``
    which closes the AITutorSession record AND deducts in one shot.
    """
    seconds = max(0, int(seconds or 0))
    if seconds == 0:
        try:
            from subscriptions.services.quota_service import get_or_create_today_quota
            return get_or_create_today_quota(user).ai_tutor_seconds_used
        except Exception:
            return 0
    try:
        from subscriptions.services.quota_service import deduct_session_seconds, get_or_create_today_quota
    except Exception:
        return seconds
    deduct_session_seconds(user, seconds)
    return get_or_create_today_quota(user).ai_tutor_seconds_used
