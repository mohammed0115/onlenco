"""Gamification audio + recent-rewards feed for the frontend.

Two public helpers:

    event_sounds_for_user(user)  → dict keyed by event_code
    recent_rewards_for(user, window_seconds=60)  → list of {event_code, ...}

The frontend includes ``_gamification_toast.html`` in the base layout;
that partial polls ``/api/v1/motivation/recent-rewards/`` on each page
load + on window focus and plays whatever rewards appear.

We respect the per-user mute toggle from Sprint 3
(``subscriptions.UserAIPreference.sound_effects_enabled``). When the
flag is off, ``audio_url`` is wiped from the response so the frontend
can still show the toast without playing sound.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable, Optional

from django.utils import timezone

from ..models import GameEventSound, UserAchievement, UserBadge, UserXP


DEFAULT_WINDOW_SECONDS = 60


def _sound_for(code: str) -> Optional[GameEventSound]:
    return GameEventSound.objects.filter(code=code, is_active=True).first()


def _sounds_enabled_for(user) -> bool:
    """User-level mute (sound effects). Defaults to True."""
    try:
        from subscriptions.models import UserAIPreference
        pref = UserAIPreference.objects.filter(user=user).first()
        if pref is None:
            return True
        return bool(pref.sound_effects_enabled)
    except Exception:
        return True


def _format_message(template: str, **kwargs) -> str:
    if not template:
        return ""
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template


def event_sounds_for_user(user) -> dict:
    """All active sounds, scrubbed of audio URLs when the user has muted.

    Returns ``{event_code: {audio_src, animation, message_en, message_ar}}``.
    """
    enabled = _sounds_enabled_for(user)
    out = {}
    for sound in GameEventSound.objects.filter(is_active=True):
        out[sound.code] = {
            "audio_src": sound.effective_audio_src if enabled else "",
            "animation": sound.animation,
            "message_en": sound.message_en,
            "message_ar": sound.message_ar,
        }
    return out


def _achievement_rewards(user, since) -> Iterable[dict]:
    sound = _sound_for("achievement_unlocked")
    if sound is None:
        return []
    rows = (
        UserAchievement.objects
        .filter(user=user, earned_at__gte=since)
        .select_related("achievement")
        .order_by("-earned_at")
    )
    out = []
    for row in rows:
        ach = row.achievement
        out.append({
            "event_code": "achievement_unlocked",
            "message_en": _format_message(sound.message_en, name=ach.name, xp=ach.xp_reward),
            "message_ar": _format_message(sound.message_ar, name=ach.name, xp=ach.xp_reward),
            "audio_src": sound.effective_audio_src,
            "animation": sound.animation,
            "xp_callout_en": _format_message(sound.xp_callout_template_en, xp=ach.xp_reward),
            "xp_callout_ar": _format_message(sound.xp_callout_template_ar, xp=ach.xp_reward),
            "earned_at": row.earned_at.isoformat(),
            "id": f"ach-{row.pk}",
            "payload": {"achievement_code": ach.code, "xp_reward": ach.xp_reward},
        })
    return out


def _badge_rewards(user, since) -> Iterable[dict]:
    sound = _sound_for("bonus") or _sound_for("achievement_unlocked")
    if sound is None:
        return []
    rows = UserBadge.objects.filter(user=user, earned_at__gte=since).order_by("-earned_at")
    out = []
    for row in rows:
        out.append({
            "event_code": "bonus",
            "message_en": f"New badge: {row.badge_name}",
            "message_ar": f"شارة جديدة: {row.badge_name}",
            "audio_src": sound.effective_audio_src,
            "animation": sound.animation,
            "xp_callout_en": "",
            "xp_callout_ar": "",
            "earned_at": row.earned_at.isoformat(),
            "id": f"badge-{row.pk}",
            "payload": {"badge_code": row.badge_code, "badge_name": row.badge_name},
        })
    return out


def _level_up_rewards(user, since) -> Iterable[dict]:
    """We don't have a dedicated level_up log table, so infer from UserXP.
    A level up emits exactly one reward per ``updated_at`` tick when
    ``level_number > 1`` and the tick lands inside the window.
    """
    sound = _sound_for("level_up")
    if sound is None:
        return []
    xp = UserXP.objects.filter(user=user).first()
    if not xp or xp.updated_at < since or xp.level_number <= 1:
        return []
    # Without per-level history we approximate: include exactly one
    # reward stamped at the row's updated_at. Idempotency comes from the
    # client de-duping on the stable ``id`` (level number + timestamp).
    return [{
        "event_code": "level_up",
        "message_en": _format_message(sound.message_en, level=xp.level_number, xp=xp.total_xp),
        "message_ar": _format_message(sound.message_ar, level=xp.level_number, xp=xp.total_xp),
        "audio_src": sound.effective_audio_src,
        "animation": sound.animation,
        "xp_callout_en": _format_message(sound.xp_callout_template_en, level=xp.level_number, xp=xp.total_xp),
        "xp_callout_ar": _format_message(sound.xp_callout_template_ar, level=xp.level_number, xp=xp.total_xp),
        "earned_at": xp.updated_at.isoformat(),
        "id": f"lvl-{xp.level_number}",
        "payload": {"level": xp.level_number, "total_xp": xp.total_xp},
    }]


def recent_rewards_for(user, *, window_seconds: int = DEFAULT_WINDOW_SECONDS) -> list[dict]:
    """Rewards earned in the last ``window_seconds`` seconds.

    Used by the frontend toast partial to celebrate fresh wins. The
    return shape is intentionally JSON-ready (no Django model
    instances) so the API endpoint just serialises the list.
    """
    if not getattr(user, "is_authenticated", False):
        return []
    since = timezone.now() - timedelta(seconds=window_seconds)
    rewards: list[dict] = []
    rewards.extend(_achievement_rewards(user, since))
    rewards.extend(_badge_rewards(user, since))
    rewards.extend(_level_up_rewards(user, since))
    if not _sounds_enabled_for(user):
        # User opted out of audio — keep the toast text + animation,
        # strip the audio so the JS plays nothing.
        for r in rewards:
            r["audio_src"] = ""
    rewards.sort(key=lambda r: r["earned_at"], reverse=True)
    return rewards
