"""Localized subject-line lookup.

Spec contract:
    get_localized_subject(event_type, language) -> str

Why this module exists separately from `notifications.constants`:
  * Constants hold the raw mappings (`SUBJECTS_AR`, `DEFAULT_SUBJECTS`).
  * This module owns the *resolution rule* — fallback chain across
    AR ↔ EN ↔ humanised event name, so a missing entry never leaks
    a raw `placement_completed` snake_case identifier into a subject line.
  * Tests can lock the resolution rule in one place.

Resolution order:
  1. Exact match in the requested language.
  2. Match in the *other* language (so a partially-localized event
     still gets a translated string instead of a fallback).
  3. Humanised event name from the text humanizer.
"""
from __future__ import annotations

import logging
from typing import Optional

from .. import constants as C

logger = logging.getLogger(__name__)


def _normalise_language(language: Optional[str]) -> str:
    """Map any input to "ar" or "en"; unknown / blank → "ar"."""
    if language and language in {"ar", "en"}:
        return language
    return "ar"


def get_localized_subject(event_type: str, language: Optional[str]) -> str:
    """Return the email subject line for `event_type` in `language`.

    Always returns a non-empty, human-readable string — never a raw
    event key like `placement_completed`."""
    lang = _normalise_language(language)
    primary = C.SUBJECTS_AR if lang == "ar" else C.DEFAULT_SUBJECTS
    secondary = C.DEFAULT_SUBJECTS if lang == "ar" else C.SUBJECTS_AR

    subject = primary.get(event_type) or secondary.get(event_type)
    if subject:
        return subject

    # Last resort — humanise the event key. Never expose the raw
    # snake_case identifier to a recipient.
    from core.services.text_humanizer import humanize_event_name
    return humanize_event_name(event_type, language=lang)


def get_user_language(user) -> str:
    """Single-call helper for "what language should I render for this user?".

    Order:
      1. NotificationPreference.language (synced to Profile on creation).
      2. Profile.preferred_language.
      3. Project default ("ar").

    Tolerates `user=None` and unauthenticated users — returns "ar"."""
    if user is None or not getattr(user, "is_authenticated", True):
        return "ar"
    # NotificationPreference is the canonical store and is sourced from
    # the profile when first created — see PreferenceService.
    try:
        from .preference_service import PreferenceService
        return _normalise_language(PreferenceService().get_language(user))
    except Exception:
        # Any DB error (rare) shouldn't block an email send.
        prof_lang = getattr(getattr(user, "profile", None), "preferred_language", None)
        return _normalise_language(prof_lang)
