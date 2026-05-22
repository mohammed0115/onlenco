"""Library Natural Reader — session + TTS + quota deduction.

Pipeline:
    1. ``prepare(text)`` → tts_ready text + chunks (no side effects).
    2. ``start_session(user, chapter)`` → opens LibraryAudioSession; refuses
       if no library quota.
    3. ``synthesize_chunk(chunk_text, voice)`` → calls upstream TTS, returns
       base64 audio. (Stateless — caller decides when to call.)
    4. ``end_session(session_id, seconds)`` → closes the row + deducts
       seconds from the library_audio bucket.

Concurrency: a partial unique constraint on LibraryAudioSession.user
WHERE status='in_progress' enforces "one active listening session per
user" at the DB level.
"""
from __future__ import annotations

import logging
from typing import Optional

from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import (
    AvatarProfile,
    LibraryAudioSession,
    TextNormalizationLog,
    VoiceProfile,
)
from . import quota_service


logger = logging.getLogger(__name__)


class LibraryQuotaExhausted(Exception):
    """Raised when the user has no remaining library audio seconds today."""


class LibraryConcurrentSessionExists(Exception):
    """Raised when the user already has a listening session open."""


def prepare(text: str, *, language: str = "en", source: str = "library_chapter", source_id: Optional[int] = None, persist_log: bool = True) -> dict:
    """Run the reading-prep pipeline. Persists a TextNormalizationLog row
    when ``persist_log`` is True so admins can audit the diff.
    """
    from core.services.reading_prep import prepare_for_reading
    result = prepare_for_reading(text or "", language=language)
    if persist_log and result["tts_ready_text"]:
        try:
            TextNormalizationLog.objects.create(
                source=source,
                source_id=source_id,
                language=language,
                original_text=text or "",
                tts_ready_text=result["tts_ready_text"],
                applied_rules=result["applied_rules"],
                original_chars=result["original_chars"],
                tts_chars=result["tts_chars"],
                estimated_seconds=result["estimated_seconds"],
            )
        except Exception:
            logger.exception("TextNormalizationLog create failed")
    return result


@transaction.atomic
def start_session(user, *, chapter_id: int, chapter_title: str = "", voice_profile: Optional[VoiceProfile] = None) -> LibraryAudioSession:
    """Open a listening session. Raises LibraryQuotaExhausted / LibraryConcurrentSessionExists."""
    if quota_service.get_remaining_library_seconds(user) <= 0:
        raise LibraryQuotaExhausted("No library audio seconds available today.")
    # Force-close any earlier in-progress session for this user before
    # opening a new one. A session left open (tab closed / navigated away
    # without calling /audio/finish/) would otherwise trip the partial
    # unique constraint and block every future "Listen" with a 409.
    # Mirrors the AI-tutor session policy (one active session, prior ones
    # force-cancelled with zero deduction).
    LibraryAudioSession.objects.filter(
        user=user, status="in_progress",
    ).update(status="cancelled", ended_at=timezone.now())
    try:
        return LibraryAudioSession.objects.create(
            user=user,
            chapter_id=chapter_id,
            chapter_title=chapter_title[:200],
            voice_profile=voice_profile,
            status="in_progress",
        )
    except IntegrityError as exc:
        raise LibraryConcurrentSessionExists(
            "A library audio session is already in progress.",
        ) from exc


def get_open_session(user) -> Optional[LibraryAudioSession]:
    return LibraryAudioSession.objects.filter(user=user, status="in_progress").first()


@transaction.atomic
def end_session(session_id: int, *, actual_seconds: int, killed_by_quota: bool = False) -> LibraryAudioSession:
    """Close a session and deduct from library quota.

    Idempotent: re-calling on an already-closed session is a noop, so
    network retries from the browser don't double-deduct.
    """
    session = LibraryAudioSession.objects.select_for_update().get(pk=session_id)
    if session.status != "in_progress":
        return session
    seconds = max(0, int(actual_seconds or 0))
    remaining = quota_service.consume_library_seconds(session.user, seconds) if seconds else quota_service.get_remaining_library_seconds(session.user)
    session.ended_at = timezone.now()
    session.duration_seconds = seconds
    session.consumed_seconds = seconds
    session.remaining_after_seconds = remaining
    session.status = "killed_quota_exceeded" if killed_by_quota else "completed"
    session.save(update_fields=[
        "ended_at", "duration_seconds", "consumed_seconds",
        "remaining_after_seconds", "status",
    ])
    return session


@transaction.atomic
def cancel_session(session_id: int) -> LibraryAudioSession:
    session = LibraryAudioSession.objects.select_for_update().get(pk=session_id)
    if session.status != "in_progress":
        return session
    session.ended_at = timezone.now()
    session.status = "cancelled"
    session.save(update_fields=["ended_at", "status"])
    return session


def synthesize_chunk(chunk_text: str, *, voice: str = "alloy", language: str = "en") -> dict:
    """Thin shim around tutor.services.tts.synthesize so library callers
    don't depend on the tutor package directly. Returns
    ``{"audio_b64", "format", "voice"}``.
    """
    try:
        from tutor.services.tts import synthesize
    except Exception:
        return {"audio_b64": "", "format": "", "voice": ""}
    # The tutor synthesize() reads AI_TTS_VOICE from settings; library
    # callers pass an explicit voice, so we override the setting via a
    # lightweight wrapper that overrides on the request payload directly.
    from django.conf import settings as dj_settings
    saved = getattr(dj_settings, "AI_TTS_VOICE", None)
    try:
        if voice:
            dj_settings.AI_TTS_VOICE = voice
        result = synthesize(chunk_text, language=language)
    finally:
        if saved is not None:
            dj_settings.AI_TTS_VOICE = saved
    return result
