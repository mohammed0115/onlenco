"""User AI preference helpers.

The tutor session calls ``resolve_voice_for(user)`` at start-time so the
provider receives the user's choice rather than a global env default.
``resolve_avatar_for(user)`` does the same for the on-screen avatar.

Both helpers degrade gracefully when:
  * the user has no preference row yet → first active VoiceProfile / AvatarProfile
  * the catalog is empty → ``None`` (caller falls back to env defaults)
"""
from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings

from ..models import AvatarProfile, UserAIPreference, VoiceProfile

logger = logging.getLogger(__name__)


class IncompatibleVoiceError(ValueError):
    """Raised when a voice gender is saved against an incompatible avatar."""


def _voice_gender(voice) -> str:
    if voice is None:
        return "neutral"
    return str(getattr(voice, "voice_type", voice) or "neutral").lower()


def _avatar_gender(avatar) -> str:
    if avatar is None:
        return "neutral"
    return str(getattr(avatar, "gender", avatar) or "neutral").lower()


def is_voice_compatible_with_avatar(voice, avatar) -> bool:
    """SINGLE SOURCE OF TRUTH for voice↔avatar gender compatibility.

    Accepts ``VoiceProfile`` / ``AvatarProfile`` objects OR plain gender
    strings. Rules:
      * Male avatar   → male or neutral voice (never female).
      * Female avatar → female or neutral voice (never male).
      * Neutral / no-image avatar → neutral voice always; other voices only
        when ``PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES`` (default True).
    """
    v = _voice_gender(voice)
    a = _avatar_gender(avatar)
    if a == "male":
        return v in ("male", "neutral")
    if a == "female":
        return v in ("female", "neutral")
    # neutral / no image avatar
    if v == "neutral":
        return True
    return bool(getattr(settings, "PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES", True))


def get_or_create_preference(user) -> UserAIPreference:
    pref, _ = UserAIPreference.objects.get_or_create(user=user)
    return pref


def _default_voice() -> Optional[VoiceProfile]:
    return VoiceProfile.objects.filter(is_active=True).order_by("sort_order", "id").first()


def _default_avatar() -> Optional[AvatarProfile]:
    return AvatarProfile.objects.filter(is_active=True).order_by("sort_order", "id").first()


def _voice_for_gender(gender: str) -> Optional[VoiceProfile]:
    g = (gender or "").lower()
    if g not in ("male", "female"):
        return None
    return (
        VoiceProfile.objects.filter(is_active=True, voice_type=g)
        .order_by("sort_order", "id")
        .first()
    )


def _gender_mismatch(voice: VoiceProfile, avatar: AvatarProfile) -> bool:
    return not is_voice_compatible_with_avatar(voice, avatar)


def default_voice_for_avatar(avatar: AvatarProfile | None) -> Optional[VoiceProfile]:
    """Best compatible default voice for an avatar — prefer the same gender,
    then neutral, then any compatible active voice."""
    if avatar is None:
        return _default_voice()
    g = _avatar_gender(avatar)
    preferred = [g, "neutral"] if g in ("male", "female") else ["neutral"]
    for vt in preferred:
        v = (VoiceProfile.objects.filter(is_active=True, voice_type=vt)
             .order_by("sort_order", "id").first())
        if v:
            return v
    for v in VoiceProfile.objects.filter(is_active=True).order_by("sort_order", "id"):
        if is_voice_compatible_with_avatar(v, avatar):
            return v
    return _default_voice()


def correct_incompatible_preference(pref: UserAIPreference | None) -> bool:
    """Heal an already-saved invalid pair by switching ONLY the voice to a
    compatible default (never touches the chosen avatar). Persists + logs.
    Returns True when a correction was made."""
    if not pref or not pref.voice_profile_id or not pref.avatar_profile_id:
        return False
    if is_voice_compatible_with_avatar(pref.voice_profile, pref.avatar_profile):
        return False
    new_voice = default_voice_for_avatar(pref.avatar_profile)
    if new_voice and new_voice.id != pref.voice_profile_id:
        logger.info(
            "preferences: auto-corrected incompatible voice user=%s "
            "avatar=%s(%s) voice %s(%s) → %s(%s)",
            pref.user_id, pref.avatar_profile.code, pref.avatar_profile.gender,
            pref.voice_profile.code, pref.voice_profile.voice_type,
            new_voice.code, new_voice.voice_type,
        )
        pref.voice_profile = new_voice
        pref.save(update_fields=["voice_profile", "updated_at"])
        return True
    return False


def resolve_voice_for(user) -> Optional[VoiceProfile]:
    """The voice that should drive this user's next tutor session.

    Spec: the chosen avatar's gender drives the voice. If the user has
    explicitly picked a voice that matches the avatar's gender, respect it
    (lets students pick between e.g. two female voices). If the explicit
    voice mismatches (female voice + male avatar), the avatar wins.
    """
    pref = (
        UserAIPreference.objects
        .select_related("voice_profile", "avatar_profile")
        .filter(user=user).first()
    )
    avatar = pref.avatar_profile if (pref and pref.avatar_profile and pref.avatar_profile.is_active) else None
    voice = pref.voice_profile if (pref and pref.voice_profile and pref.voice_profile.is_active) else None

    if voice and avatar and _gender_mismatch(voice, avatar):
        aligned = _voice_for_gender(avatar.gender)
        if aligned:
            return aligned
    if voice:
        return voice
    if avatar:
        aligned = _voice_for_gender(avatar.gender)
        if aligned:
            return aligned
    return _default_voice()


def resolve_avatar_for(user) -> Optional[AvatarProfile]:
    pref = UserAIPreference.objects.select_related("avatar_profile").filter(user=user).first()
    if pref and pref.avatar_profile and pref.avatar_profile.is_active:
        return pref.avatar_profile
    return _default_avatar()


def set_preference(
    user,
    *,
    voice_code: str | None = None,
    avatar_code: str | None = None,
    speed: str | None = None,
    pitch: str | None = None,
    sound_effects_enabled: bool | None = None,
) -> UserAIPreference:
    """Update one or more fields on the user's preference row.

    Unknown / inactive codes are *silently ignored* — we don't want a
    typo in the request payload to wipe the user's prior selection.

    Gender compatibility is ENFORCED here (backend source of truth):
      * An explicitly-picked voice that is incompatible with the (new or
        existing) avatar is REJECTED with ``IncompatibleVoiceError``.
      * When only the avatar changes and the saved voice no longer fits, the
        voice is auto-switched to a compatible default (no error).
    """
    pref = get_or_create_preference(user)
    fields = []

    new_voice = VoiceProfile.objects.filter(code=voice_code, is_active=True).first() if voice_code else None
    new_avatar = AvatarProfile.objects.filter(code=avatar_code, is_active=True).first() if avatar_code else None
    final_avatar = new_avatar or (pref.avatar_profile if pref.avatar_profile_id else None)
    final_voice = new_voice or (pref.voice_profile if pref.voice_profile_id else None)

    if final_avatar and final_voice and not is_voice_compatible_with_avatar(final_voice, final_avatar):
        if new_voice is not None:
            # The user explicitly chose an incompatible voice → reject.
            raise IncompatibleVoiceError("voice_incompatible_with_avatar")
        # Only the avatar changed; the saved voice no longer fits → correct it.
        final_voice = default_voice_for_avatar(final_avatar) or final_voice

    if new_avatar is not None and pref.avatar_profile_id != new_avatar.id:
        pref.avatar_profile = new_avatar
        fields.append("avatar_profile")
    if final_voice is not None and pref.voice_profile_id != final_voice.id:
        pref.voice_profile = final_voice
        fields.append("voice_profile")

    if speed and speed in dict(UserAIPreference.SPEED_CHOICES):
        pref.speed = speed
        fields.append("speed")
    if pitch and pitch in dict(UserAIPreference.PITCH_CHOICES):
        pref.pitch = pitch
        fields.append("pitch")
    if sound_effects_enabled is not None:
        pref.sound_effects_enabled = bool(sound_effects_enabled)
        fields.append("sound_effects_enabled")
    if fields:
        fields.append("updated_at")
        pref.save(update_fields=fields)
    return pref


def preference_snapshot(user) -> dict:
    """Shape used by the preferences page + JSON API."""
    pref = UserAIPreference.objects.select_related(
        "voice_profile", "avatar_profile",
    ).filter(user=user).first()
    # Safely heal a previously-saved invalid voice/avatar combination so the
    # page never shows a mismatched voice as "selected".
    correct_incompatible_preference(pref)
    voice = pref.voice_profile if pref else None
    avatar = pref.avatar_profile if pref else None
    if voice is None or not voice.is_active:
        voice = _default_voice()
    if avatar is None or not avatar.is_active:
        avatar = _default_avatar()
    return {
        "voice": {
            "code": voice.code if voice else None,
            "name_en": voice.name_en if voice else None,
            "name_ar": voice.name_ar if voice else None,
            "provider_voice_id": voice.provider_voice_id if voice else None,
            "voice_type": voice.voice_type if voice else None,
            "style": voice.style if voice else None,
            "accent": voice.accent if voice else None,
            "tone": voice.tone if voice else None,
        },
        "avatar": {
            "code": avatar.code if avatar else None,
            "name_en": avatar.name_en if avatar else None,
            "name_ar": avatar.name_ar if avatar else None,
            "image_url": avatar.effective_image_url if avatar else None,
            "gender": avatar.gender if avatar else None,
            "style": avatar.style if avatar else None,
        },
        "speed": pref.speed if pref else "normal",
        "pitch": pref.pitch if pref else "normal",
        "sound_effects_enabled": pref.sound_effects_enabled if pref else True,
    }
