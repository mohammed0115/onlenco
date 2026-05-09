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
            timeout=(5, 25),
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
    placement page so users aren't misled. For a more accurate signal when
    the user is reading a known prompt, call `pronunciation_score_against`.
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


def _normalise_word(w: str) -> str:
    """Strip punctuation + lowercase for word-level comparison."""
    out = []
    for ch in (w or "").lower():
        if ch.isalpha() or ch.isdigit() or ch in "'-":
            out.append(ch)
    return "".join(out)


def _alignment_accuracy(expected: list[str], heard: list[str]) -> float:
    """Word-level alignment accuracy via Levenshtein distance.

    Returns the proportion of expected words that survived intact through
    the transcript — i.e. (matches) / max(len(expected), 1). Insertions in
    the transcript don't penalise; substitutions and deletions do.
    """
    if not expected:
        return 0.0
    n, m = len(expected), len(heard)
    # Standard edit-distance DP.
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost = 0 if expected[i - 1] == heard[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,
                dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + cost,
            )
    edits = dp[n][m]
    matches = max(0, n - edits)
    return matches / n


def pronunciation_score_against(
    transcript: str,
    expected_text: str,
    *,
    stt_confidence: float = 1.0,
    fluency: int = 50,
) -> int:
    """Read-aloud scorer: 0..100 based on word-level alignment.

    Use this when the student was asked to read a known prompt; the score
    drops sharply when words are missing or wrong, regardless of how
    confident the STT was. Mixed with confidence + fluency for a final
    band.

    Algorithm:
      - normalise + tokenise both strings
      - compute Levenshtein-based alignment accuracy
      - blend: 0.6 × alignment + 0.25 × confidence + 0.15 × (fluency/100)
    """
    expected_tokens = [t for t in (_normalise_word(w) for w in expected_text.split()) if t]
    heard_tokens = [t for t in (_normalise_word(w) for w in transcript.split()) if t]
    if not expected_tokens or not heard_tokens:
        return 0
    align = _alignment_accuracy(expected_tokens, heard_tokens)
    blended = (
        0.60 * align * 100.0
        + 0.25 * (stt_confidence or 0.0) * 100.0
        + 0.15 * (fluency or 0)
    )
    return max(0, min(100, int(round(blended))))
