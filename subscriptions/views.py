"""User-facing pages: upgrade screen, preferences, JSON quota snapshot."""
from __future__ import annotations

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import AvatarProfile, SubscriptionPlan, VoiceProfile
from .services import preference_service, quota_service, subscription_service


@login_required
def upgrade_page(request):
    """List available paid plans and the user's current quota snapshot."""
    plans = SubscriptionPlan.objects.filter(
        is_active=True, is_free_trial=False,
    ).order_by("sort_order", "ai_tutor_daily_minutes")
    current_plan = subscription_service.active_plan_for(request.user)
    snapshot = quota_service.quota_snapshot(request.user)
    return render(request, "subscriptions/upgrade.html", {
        "plans": plans,
        "current_plan": current_plan,
        "snapshot": snapshot,
    })


@login_required
def quota_snapshot_api(request):
    """JSON endpoint the tutor screen polls to render the remaining indicator."""
    return JsonResponse(quota_service.quota_snapshot(request.user))


@login_required
def preferences_page(request):
    """Voice + avatar + speed/pitch preferences. POST to save."""
    if request.method == "POST":
        try:
            preference_service.set_preference(
                request.user,
                voice_code=request.POST.get("voice_code"),
                avatar_code=request.POST.get("avatar_code"),
                speed=request.POST.get("speed"),
                pitch=request.POST.get("pitch"),
                sound_effects_enabled=("sound_effects_enabled" in request.POST),
            )
            messages.success(request, "Preferences saved.")
        except preference_service.IncompatibleVoiceError:
            lang = getattr(request, "LANGUAGE_CODE", "en") or "en"
            messages.error(request, (
                "هذا الصوت غير متوافق مع الشخصية المختارة."
                if str(lang).startswith("ar") else
                "This voice is not compatible with the selected avatar."
            ))
        return redirect("subscriptions:preferences")

    voices = VoiceProfile.objects.filter(is_active=True).order_by("sort_order", "name_en")
    avatars = AvatarProfile.objects.filter(is_active=True).order_by("sort_order", "name_en")
    snapshot = preference_service.preference_snapshot(request.user)
    from django.conf import settings as dj_settings
    return render(request, "subscriptions/preferences.html", {
        "voices": voices,
        "avatars": avatars,
        "snapshot": snapshot,
        "neutral_allows_all": bool(getattr(
            dj_settings, "PREFERENCES_NEUTRAL_AVATAR_ALLOWS_ALL_VOICES", True)),
    })


@login_required
def preference_api(request):
    """JSON GET/POST for the tutor screen.

    GET → current snapshot.
    POST → update one or more fields (any of voice_code, avatar_code, speed, pitch).
    """
    if request.method == "POST":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            payload = {}
        try:
            preference_service.set_preference(
                request.user,
                voice_code=payload.get("voice_code"),
                avatar_code=payload.get("avatar_code"),
                speed=payload.get("speed"),
                pitch=payload.get("pitch"),
                sound_effects_enabled=payload.get("sound_effects_enabled"),
            )
        except preference_service.IncompatibleVoiceError:
            lang = getattr(request, "LANGUAGE_CODE", "en") or "en"
            return JsonResponse({
                "error": "voice_incompatible_with_avatar",
                "message": (
                    "هذا الصوت غير متوافق مع الشخصية المختارة."
                    if str(lang).startswith("ar") else
                    "This voice is not compatible with the selected avatar."
                ),
            }, status=400)
    return JsonResponse(preference_service.preference_snapshot(request.user))
