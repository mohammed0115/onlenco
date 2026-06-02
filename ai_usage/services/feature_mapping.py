"""Canonical feature + role mapping for AI usage attribution.

Every migrated AI call maps to exactly ONE feature constant here, so the
dashboard and reports speak a single vocabulary. Re-exports the feature
codes from ``ai_usage.constants`` and adds the small derivation helpers the
call sites use (challenge interaction_type → feature, user → role).
"""
from __future__ import annotations

from .. import constants as C

# --- canonical feature constants (single source = constants.py) ---------
PLACEMENT_WRITTEN = C.FEATURE_PLACEMENT_WRITTEN
PLACEMENT_SPEAKING = C.FEATURE_PLACEMENT_SPEAKING
AI_TUTOR = C.FEATURE_AI_TUTOR
LESSON_ASSISTANT = C.FEATURE_LESSON_ASSISTANT
VOCABULARY = C.FEATURE_VOCABULARY
LIBRARY = C.FEATURE_LIBRARY
MOTIVATION = C.FEATURE_MOTIVATION
CONTENT_GENERATION = C.FEATURE_CONTENT_GENERATION
CHALLENGE_EXPLANATION = C.FEATURE_CHALLENGE_EXPLANATION
CHALLENGE_ROLEPLAY = C.FEATURE_CHALLENGE_ROLEPLAY
CHALLENGE_END_ADVICE = C.FEATURE_CHALLENGE_END_ADVICE
READING_LISTENING = C.FEATURE_READING_LISTENING
OTHER = C.FEATURE_OTHER

# 12A.1 dedicated audio/media feature codes (added to FEATURE_CHOICES).
STT = C.FEATURE_STT                       # transcription (speaking input)
TTS = C.FEATURE_TTS                       # speech output (listening)
MEDIA_GENERATION = C.FEATURE_MEDIA_GENERATION
DICTIONARY = C.FEATURE_VOCABULARY

# Challenge interaction_type (tutor.services) → canonical feature.
CHALLENGE_INTERACTION_TO_FEATURE = {
    "wrong_answer_explanation": CHALLENGE_EXPLANATION,
    "speaking_feedback": CHALLENGE_EXPLANATION,
    "mistake_explanation": CHALLENGE_EXPLANATION,
    "end_advice": CHALLENGE_END_ADVICE,
    "roleplay": CHALLENGE_ROLEPLAY,
}


def feature_for_challenge(interaction_type: str) -> str:
    return CHALLENGE_INTERACTION_TO_FEATURE.get(interaction_type, CHALLENGE_EXPLANATION)


def role_for_user(user, *, default: str = C.ROLE_STUDENT) -> str:
    """Derive role from the user's profile/groups.

    No/anonymous user → system (scheduled/background). Admins via
    profile.is_admin (or is_staff/superuser). Teachers via profile.is_teacher
    when not also a student. Otherwise the supplied default (student)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return C.ROLE_SYSTEM
    if getattr(user, "is_superuser", False):
        return C.ROLE_ADMIN
    profile = getattr(user, "profile", None)
    if profile is None:
        return default
    try:
        if profile.is_admin:
            return C.ROLE_ADMIN
        if profile.is_teacher and not profile.is_student:
            return C.ROLE_TEACHER
    except Exception:
        pass
    return default
