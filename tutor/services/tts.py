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
        resp = requests.post(
            f"{settings.AI_API_BASE.rstrip('/')}/audio/speech",
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=(5, 15),
        )
        resp.raise_for_status()
        audio_b64 = base64.b64encode(resp.content).decode("ascii")
        try:
            from core.services.ai_usage import log_usage
            log_usage(None, "tutor", model=payload["model"], success=True)
        except Exception:
            pass
        return {"audio_b64": audio_b64, "format": payload["format"], "voice": payload["voice"]}
    except Exception as e:
        logger.warning("TTS call failed: %s", e)
        try:
            from core.services.ai_usage import log_usage
            log_usage(
                None, "tutor", model=payload.get("model", ""),
                success=False, error_message=str(e),
            )
        except Exception:
            pass
        return {"audio_b64": "", "format": "", "voice": ""}
