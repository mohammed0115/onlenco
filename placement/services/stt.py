"""Speech-to-text adapter.

Calls an OpenAI-compatible Whisper endpoint when `AI_API_KEY` is set.
Falls back to a deterministic stub returning empty text + zero confidence
so flows never crash without a configured API.

Public:
    transcribe(audio_file) -> dict {transcript, duration_seconds, confidence}
"""
from __future__ import annotations

import logging
import math

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _stub_response(audio_file) -> dict:
    size = getattr(audio_file, "size", 0)
    # Crude duration estimate: assume ~16 kbps audio. Only used as a placeholder.
    duration = max(1, int(size / 2000)) if size else 0
    return {
        "transcript": "",
        "duration_seconds": duration,
        "confidence": 0.0,
    }


def transcribe(audio_file) -> dict:
    if not settings.AI_API_KEY or audio_file is None:
        return _stub_response(audio_file)

    audio_file.seek(0)
    name = getattr(audio_file, "name", "audio.webm")
    try:
        resp = requests.post(
            f"{settings.AI_API_BASE.rstrip('/')}/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {settings.AI_API_KEY}",
            },
            files={"file": (name, audio_file.read())},
            data={
                "model": getattr(settings, "AI_STT_MODEL", "whisper-1"),
                "response_format": "verbose_json",
            },
            timeout=60,
        )
        resp.raise_for_status()
        body = resp.json()
        transcript = (body.get("text") or "").strip()
        duration = int(round(body.get("duration", 0) or 0))
        confidence = 1.0 if transcript else 0.0
        try:
            from core.services.ai_usage import log_usage
            log_usage(
                None, "placement",
                model=getattr(settings, "AI_STT_MODEL", "whisper-1"),
                success=True,
            )
        except Exception:
            pass
        return {
            "transcript": transcript,
            "duration_seconds": duration,
            "confidence": confidence,
        }
    except Exception as e:
        logger.warning("STT call failed: %s", e)
        try:
            from core.services.ai_usage import log_usage
            log_usage(
                None, "placement",
                model=getattr(settings, "AI_STT_MODEL", "whisper-1"),
                success=False, error_message=str(e),
            )
        except Exception:
            pass
        return _stub_response(audio_file)


def fluency_score(transcript: str, duration_seconds: int) -> int:
    """Rough WPM-based fluency score 0..100. >130 wpm → 100; <50 wpm → 0."""
    if not transcript or duration_seconds <= 0:
        return 0
    words = len([w for w in transcript.split() if w])
    minutes = duration_seconds / 60.0
    wpm = words / minutes if minutes > 0 else 0
    return max(0, min(100, int(round((wpm - 50.0) / 80.0 * 100))))


def pronunciation_score(transcript: str, stt_confidence: float, fluency: int) -> int:
    """Heuristic 0..100 derived from STT confidence + fluency + length.

    A real phoneme-level model is out of scope; this proxy correlates with
    intelligibility well enough to band students. Documented as such on the
    placement page so users aren't misled.
    """
    if not transcript:
        return 0
    word_count = len(transcript.split())
    length_signal = min(word_count / 30.0, 1.0)
    score = (
        0.6 * (stt_confidence or 0.0) * 100.0
        + 0.3 * fluency
        + 0.1 * length_signal * 100.0
    )
    return max(0, min(100, int(round(score))))
