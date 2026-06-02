"""Text-to-speech adapter.

Calls an OpenAI-compatible `/audio/speech` endpoint to synthesize the
tutor reply when `AI_API_KEY` is configured. Returns a base64-encoded
audio payload (mp3 by default) so callers can ship it back in JSON.

If unconfigured or on failure, returns an empty payload — the caller
shows the text reply only.
"""
from __future__ import annotations

import base64
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_VOICE = "alloy"
DEFAULT_FORMAT = "mp3"


def synthesize(text: str, *, language: str = "en") -> dict:
    """Synthesise speech.

    Defence-in-depth: ALWAYS runs ``humanize_for_speech`` on the input
    before sending it upstream, regardless of whether the caller already
    sanitised. This guards every TTS path — chat, daily-learning audio
    command, ad-hoc admin scripts — so raw technical identifiers
    (``user_answer``, ``UA_*``, ``cefr_level``) cannot leak into a
    recording even when a future caller forgets to pre-sanitise.
    """
    if not settings.AI_API_KEY or not text:
        return {"audio_b64": "", "format": "", "voice": ""}

    # Inline import keeps this module free of a hard core dependency.
    from core.services.text_humanizer import humanize_for_speech
    text = humanize_for_speech(text, language=language) or text

    payload = {
        "model": getattr(settings, "AI_TTS_MODEL", "tts-1"),
        "input": text[:3000],
        "voice": getattr(settings, "AI_TTS_VOICE", DEFAULT_VOICE),
        "format": getattr(settings, "AI_TTS_FORMAT", DEFAULT_FORMAT),
    }
    try:
        # Centralised ai_usage wrapper (Prompt 12A.1): logs TTS audio output
        # seconds + cost. Returns raw audio bytes.
        from ai_usage.services import ai_client, feature_mapping

        audio_bytes = ai_client.synthesize_speech(
            text[:3000], voice=payload["voice"],
            feature=feature_mapping.TTS, model=payload["model"],
            response_format=payload["format"], timeout=(5, 15),
            metadata={"caller": "tutor_reply"},
        )
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        return {"audio_b64": audio_b64, "format": payload["format"], "voice": payload["voice"]}
    except Exception as e:
        logger.warning("TTS call failed: %s", e)
        return {"audio_b64": "", "format": "", "voice": ""}
