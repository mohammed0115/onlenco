"""User AI preference helpers.

The tutor session calls ``resolve_voice_for(user)`` at start-time so the
provider receives the user's choice rather than a global env default.
``resolve_avatar_for(user)`` does the same for the on-screen avatar.

Both helpers degrade gracefully when:
  * the user has no preference row yet → first active VoiceProfile / AvatarProfile
  * the catalog is empty → ``None`` (caller falls back to env defaults)
"""
from __future__ import annotations

from typing import Optional

from ..models import AvatarProfile, UserAIPreference, VoiceProfile


def get_or_create_preference(user) -> UserAIPreference:
    pref, _ = UserAIPreference.objects.get_or_create(user=user)
    return pref


def _default_voice() -> Optional[VoiceProfile]:
    return VoiceProfile.objects.filter(is_active=True).order_by("sort_order", "id").first()


def _default_avatar() -> Optional[AvatarProfile]:
    return AvatarProfile.objects.filter(is_active=True).order_by("sort_order", "id").first()


def resolve_voice_for(user) -> Optional[VoiceProfile]:
    """The voice that should drive this user's next tutor session."""
    pref = UserAIPreference.objects.select_related("voice_profile").filter(user=user).first()
    if pref and pref.voice_profile and pref.voice_profile.is_active:
        return pref.voice_profile
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
    """
    pref = get_or_create_preference(user)
    fields = []
    if voice_code:
        v = VoiceProfile.objects.filter(code=voice_code, is_active=True).first()
        if v:
            pref.voice_profile = v
            fields.append("voice_profile")
    if avatar_code:
        a = AvatarProfile.objects.filter(code=avatar_code, is_active=True).first()
        if a:
            pref.avatar_profile = a
            fields.append("avatar_profile")
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
