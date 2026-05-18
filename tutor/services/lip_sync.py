"""Lip-sync provider interface — pluggable talking-head backends.

Sprint 3 promised "human-like avatar with mouth movement". The
audio-reactive CSS overlay (Web Audio analyser → CSS scale) handles the
voice-call frame today. For **true muscle-accurate lip-sync** to a
specific photo you need one of:

  * **D-ID Talks Stream API** (paid, ~$0.05–0.10/min) — real-time WebRTC
    talking head; takes ``photo + audio`` and returns a live video
    stream. Set ``LIP_SYNC_PROVIDER=did`` + ``DID_API_KEY``.
  * **HeyGen Interactive Avatar** (paid). Similar — interactive avatar
    over WebRTC.
  * **SadTalker / Wav2Lip** (open-source, self-hosted GPU). Generates
    per-clip MP4 from photo + audio. Not real-time; queue-based.
  * **None / fallback** — the audio-reactive CSS mouth + eye-blinks we
    ship today. No external dependency.

This module exposes a single ``get_provider()`` so the rest of the code
never branches on which backend is in use. Today every backend except
``mock`` and ``css_only`` returns ``None`` until an API key arrives.
"""
from __future__ import annotations

import logging
from typing import Optional, Protocol

from django.conf import settings


logger = logging.getLogger(__name__)


class LipSyncProvider(Protocol):
    """A backend that turns ``(photo, audio_stream)`` into a video stream."""

    name: str

    def is_available(self) -> bool: ...

    def create_stream_session(self, *, avatar_image_url: str, voice: str, language: str) -> Optional[dict]:
        """Return the WebRTC / streaming credentials the browser needs, or None."""
        ...


class CssOnlyProvider:
    """Default — no external provider; rely on the audio-reactive mouth."""

    name = "css_only"

    def is_available(self) -> bool:
        return True

    def create_stream_session(self, *, avatar_image_url, voice, language):
        return {
            "provider": self.name,
            "supported": True,
            "stream_url": "",
            "session_id": "",
            "note": "Browser handles audio-reactive mouth animation locally.",
        }


class DIDProvider:
    """Stub for D-ID Talks Stream. Real implementation in a future sprint
    once ``DID_API_KEY`` is in env. Today returns ``is_available=False``.

    Reference: https://docs.d-id.com/reference/talks-stream-api
    """

    name = "did"

    def is_available(self) -> bool:
        return bool(getattr(settings, "DID_API_KEY", ""))

    def create_stream_session(self, *, avatar_image_url, voice, language):
        if not self.is_available():
            return None
        logger.warning(
            "lip_sync.DIDProvider: API integration not implemented yet. "
            "Set DID_API_KEY and wire the /talks/streams endpoint here."
        )
        return None


class HeyGenProvider:
    """Stub for HeyGen Interactive Avatar."""

    name = "heygen"

    def is_available(self) -> bool:
        return bool(getattr(settings, "HEYGEN_API_KEY", ""))

    def create_stream_session(self, *, avatar_image_url, voice, language):
        if not self.is_available():
            return None
        logger.warning(
            "lip_sync.HeyGenProvider: API integration not implemented yet. "
            "Set HEYGEN_API_KEY and wire the streaming SDK here."
        )
        return None


_REGISTRY: dict[str, type] = {
    CssOnlyProvider.name: CssOnlyProvider,
    DIDProvider.name: DIDProvider,
    HeyGenProvider.name: HeyGenProvider,
}


def get_provider() -> LipSyncProvider:
    """Resolve the configured provider, falling back to CSS-only."""
    preferred = (getattr(settings, "LIP_SYNC_PROVIDER", "css_only") or "css_only").lower()
    cls = _REGISTRY.get(preferred, CssOnlyProvider)
    provider = cls()
    if not provider.is_available():
        # Configured provider not ready — degrade gracefully.
        return CssOnlyProvider()
    return provider


def describe_capabilities() -> dict:
    """Diagnostic helper for the Control Center."""
    provider = get_provider()
    return {
        "active_provider": provider.name,
        "providers": {
            name: cls().is_available() for name, cls in _REGISTRY.items()
        },
    }
