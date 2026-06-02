"""Thin wrappers over OpenAI's image-generation + TTS endpoints.

Returns raw bytes (PNG / MP3) so the calling management commands can
hand them to Django's `FileField.save(name, ContentFile(bytes))` without
worrying about IO.

These functions read `settings.AI_API_KEY` and `settings.AI_API_BASE`
exactly the same way `placement.services._assessor.assess` does — so
they pick up the same configured key the rest of the project uses.

Costs (Beginner pack, rough):
  - DALL-E 3 standard 1024×1024: $0.04 / image × 192 prompts = ~$7.68 if
    we generate ALL prompt types. The default command only generates
    `cover` for cost control (48 × $0.04 = $1.92).
  - TTS-1 standard: $15 / 1M chars × ~57k chars across 288 scripts
    ≈ $0.86 for the full audio batch.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
import logging

import requests
from django.conf import settings


logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    ok: bool
    bytes_: bytes = b""
    cost_estimate_usd: float = 0.0
    error: str = ""


# Voice mapping for TTS — `voice_style` from LessonAudioScript → OpenAI voice id.
# All voices are en-US neutral. Two female + two male per the method spec.
VOICE_BY_STYLE = {
    "friendly_teacher": "nova",     # warm, mid-pitch female
    "slow_beginner":    "shimmer",  # softer, slower female cadence
    "dialogue":         "echo",     # neutral male — used for second voice in dialogue
    # Fallback when the seed has an unmapped style.
    "_default": "nova",
}


def _api_base() -> str:
    return (settings.AI_API_BASE or "https://api.openai.com/v1").rstrip("/")


def _api_key() -> str:
    return getattr(settings, "AI_API_KEY", "") or ""


def generate_image(prompt: str, *, size: str = "1024x1024",
                   model: str = "gpt-image-1-mini") -> GenerationResult:
    """Call OpenAI image-generation with `prompt`, return PNG bytes.

    Default model is `gpt-image-1-mini` — the cheapest image model on the
    current account (~$0.005/image vs DALL-E 3 at $0.04). The plain
    `dall-e-3` model is gone from this org; `gpt-image-*` is its
    replacement family.

    The prompt is appended with our brand-safety preamble so we never
    accidentally reproduce DK's trade dress.
    """
    if not _api_key():
        return GenerationResult(ok=False, error="AI_API_KEY not configured")

    full_prompt = (
        f"{prompt} "
        "Style: flat illustration, soft pastel background, clean 2px outlines, "
        "no text in image, no DK or DK-style trade dress, original characters only."
    )

    try:
        # Centralised ai_usage wrapper (Prompt 12A.1): media_generation,
        # role=system. cost_estimate_usd below is the historical business
        # estimate kept for backward-compat; ai_usage prices from AIModelPricing.
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        png = ai_client.generate_image(
            full_prompt[:3800], size=size, model=model,
            feature=AC.FEATURE_MEDIA_GENERATION, role=AC.ROLE_SYSTEM,
            metadata={"kind": "image"},
        )
        return GenerationResult(
            ok=True,
            bytes_=png,
            cost_estimate_usd=0.005 if "mini" in model else 0.04,
        )
    except Exception as e:
        logger.exception("image generation failed for prompt %r", prompt[:60])
        return GenerationResult(ok=False, error=str(e))


def generate_audio(text: str, *, voice_style: str = "friendly_teacher",
                   model: str = "tts-1") -> GenerationResult:
    """Call OpenAI TTS with `text`, return MP3 bytes.

    `voice_style` is the value stored on `LessonAudioScript.voice_style`;
    we map it onto an OpenAI voice id via `VOICE_BY_STYLE`.
    """
    if not _api_key():
        return GenerationResult(ok=False, error="AI_API_KEY not configured")
    if not text or not text.strip():
        return GenerationResult(ok=False, error="empty script")

    voice = VOICE_BY_STYLE.get(voice_style, VOICE_BY_STYLE["_default"])

    try:
        # Centralised ai_usage wrapper (Prompt 12A.1): media_generation TTS,
        # role=system. cost_estimate_usd preserves the historical $15/1M-char
        # business estimate; ai_usage prices from AIModelPricing.
        from ai_usage import constants as AC
        from ai_usage.services import ai_client

        audio = ai_client.synthesize_speech(
            text[:4000], voice=voice, model=model,
            feature=AC.FEATURE_MEDIA_GENERATION, role=AC.ROLE_SYSTEM,
            response_format="mp3", timeout=60, metadata={"kind": "lesson_audio"},
        )
        return GenerationResult(
            ok=True,
            bytes_=audio,
            cost_estimate_usd=len(text) * 15.0 / 1_000_000,
        )
    except Exception as e:
        logger.exception("audio generation failed (style=%s)", voice_style)
        return GenerationResult(ok=False, error=str(e))


# ---------------------------------------------------------------------------
# Text cleaning — strips HTML / placeholders before TTS so the audio
# doesn't say "less than h3 greater than" or "underscore underscore".
# ---------------------------------------------------------------------------

import re

_HTML_TAG_RE   = re.compile(r"<[^>]+>")
_UNDERSCORE_RE = re.compile(r"_{2,}")
_PLACEHOLDER_RE = re.compile(
    r"\(populated[^)]*\)|\(yuعبأ[^)]*\)|\bTODO\b|\bPENDING\b",
    re.IGNORECASE,
)


def clean_script_for_tts(text: str) -> str:
    """Return a clean, speakable version of `text`.

    - Strips HTML tags (audio shouldn't say `<h3>`).
    - Collapses long underscores to the word 'blank' (used in fill-gaps).
    - Removes placeholder markers so we don't say 'populated in P12'.
    - Compresses whitespace.
    """
    cleaned = _HTML_TAG_RE.sub(" ", text or "")
    cleaned = _UNDERSCORE_RE.sub(" blank ", cleaned)
    cleaned = _PLACEHOLDER_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned
