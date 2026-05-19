from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import TutorConversation, TutorMessage
from .services import chat


def _require_subscription(request):
    if request.user.profile.is_subscribed:
        return None
    messages.warning(request, "Subscribe to chat with the AI tutor.")
    return redirect("subscribe")


@login_required
def conversation_list(request):
    locked = _require_subscription(request)
    if locked:
        return locked

    # Hide drafts (no messages yet) so the list only shows resumable chats.
    conversations = (
        TutorConversation.objects
        .filter(user=request.user, messages__isnull=False)
        .distinct()
    )
    return render(request, "tutor/list.html", {"conversations": conversations})


@login_required
@require_POST
def new_conversation(request):
    locked = _require_subscription(request)
    if locked:
        return locked

    topic = (request.POST.get("topic") or "").strip()

    # Reuse any existing empty conversation rather than accumulating drafts.
    existing_empty = (
        TutorConversation.objects
        .filter(user=request.user, messages__isnull=True)
        .order_by("-updated_at")
        .first()
    )
    if existing_empty:
        if topic and existing_empty.topic != topic:
            existing_empty.topic = topic
            existing_empty.save(update_fields=["topic"])
        return redirect("tutor_detail", pk=existing_empty.pk)

    conv = TutorConversation.objects.create(user=request.user, topic=topic)
    return redirect("tutor_detail", pk=conv.pk)


@login_required
def conversation_detail(request, pk):
    locked = _require_subscription(request)
    if locked:
        return locked

    conv = get_object_or_404(TutorConversation, pk=pk, user=request.user)
    # Expose the EN+AR humanizer glossaries so the front-end TTS sanitiser
    # can clean text consistently when the /tutor/sanitize/ endpoint is
    # unreachable.
    from core.services.text_humanizer import (
        _merged_event_glossary,
        _merged_field_glossary,
    )
    from .services.sidebar_context import build_sidebar_payload

    humanizer_glossary = {
        "events_en": _merged_event_glossary("en"),
        "events_ar": _merged_event_glossary("ar"),
        "fields_en": _merged_field_glossary("en"),
        "fields_ar": _merged_field_glossary("ar"),
    }
    return render(request, "tutor/detail.html", {
        "conversation": conv,
        "humanizer_glossary_json": humanizer_glossary,
        "sidebar": build_sidebar_payload(request.user),
    })


@login_required
@require_POST
def send_message(request, pk):
    locked = _require_subscription(request)
    if locked:
        return locked

    conv = get_object_or_404(TutorConversation, pk=pk, user=request.user)
    text = (request.POST.get("message") or "").strip()
    if not text:
        messages.error(request, "Message cannot be empty.")
        return redirect("tutor_detail", pk=conv.pk)

    # `speaking_seconds` is sent by the front-end when the user submits via
    # the mic/auto-send path. Used to credit `speaking_minutes` on the
    # daily activity snapshot. Optional + bounded.
    try:
        speaking_seconds = max(0, min(int(request.POST.get("speaking_seconds") or 0), 3600))
    except (TypeError, ValueError):
        speaking_seconds = 0

    TutorMessage.objects.create(conversation=conv, role="user", content=text)

    if not conv.title:
        conv.title = " ".join(text.split()[:8])[:200]
        conv.save(update_fields=["title"])

    # Voice mode = the user submitted speech (mic transcript). The chat
    # service uses this to enforce a shorter, speech-friendly reply.
    reply = chat(conv, text, voice=speaking_seconds > 0)
    TutorMessage.objects.create(conversation=conv, role="assistant", content=reply)

    # Credit speaking minutes + writing attempt to today's snapshot before
    # the motivation engine runs, so xp/achievements see the new totals.
    try:
        from motivation.services import activity_collector
        snap = activity_collector.collect_daily_activity(request.user)
        updates = []
        if speaking_seconds > 0:
            snap.speaking_minutes = (snap.speaking_minutes or 0) + max(1, speaking_seconds // 60)
            updates.append("speaking_minutes")
        snap.writing_attempts = (snap.writing_attempts or 0) + 1
        updates.append("writing_attempts")
        snap.save(update_fields=updates + ["updated_at"])
    except Exception:
        import logging
        logging.getLogger(__name__).exception("tutor: activity credit failed")

    # Best-effort motivation refresh — never blocks chat.
    try:
        from motivation.services.motivation_engine import run_for_user
        run_for_user(request.user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("tutor: motivation engine failed")

    return redirect("tutor_detail", pk=conv.pk)


@login_required
def voice_call_page(request, pk):
    """Render the live voice-call page for a single conversation."""
    locked = _require_subscription(request)
    if locked:
        return locked
    conv = get_object_or_404(TutorConversation, pk=pk, user=request.user)
    from tutor.services.realtime_session import daily_minute_cap_remaining
    # Pull the user's avatar + voice preference (Sprint 3) so the page
    # can render the human-like presenter the spec asked for, instead of
    # just a phone orb.
    avatar = None
    voice = None
    try:
        from subscriptions.services import preference_service
        avatar = preference_service.resolve_avatar_for(request.user)
        voice = preference_service.resolve_voice_for(request.user)
    except Exception:
        pass
    # Strip the "— Friendly Teacher" suffix so the title bar / UI can
    # use the bare first name (Layla / Omar / Sara).
    def _first(name):
        return (name or "").split("—", 1)[0].strip()
    tutor_name_en = _first(getattr(avatar, "name_en", "")) or "Layla"
    tutor_name_ar = _first(getattr(avatar, "name_ar", "")) or "ليلى"
    return render(request, "tutor/voice_call.html", {
        "conversation": conv,
        "minutes_remaining": daily_minute_cap_remaining(request.user),
        "avatar": avatar,
        "voice": voice,
        "tutor_name_en": tutor_name_en,
        "tutor_name_ar": tutor_name_ar,
    })


@login_required
def voice_call_quick(request):
    """Dashboard one-click entry point: pick or create a conversation
    and go straight to the voice-call page. Lets the dashboard card
    read 'Voice call' without needing the user to first open a chat.
    """
    locked = _require_subscription(request)
    if locked:
        return locked
    # Reuse the most recent conversation if one exists; otherwise create
    # a fresh one so the page always has a context to attach turns to.
    conv = (
        TutorConversation.objects
        .filter(user=request.user)
        .order_by("-updated_at")
        .first()
    )
    if conv is None:
        conv = TutorConversation.objects.create(user=request.user)
    return redirect("tutor_voice_call", pk=conv.pk)


@login_required
@require_POST
def sanitize_for_speech(request):
    """Return the speech-safe version of the supplied text.

    Called by the tutor TTS front-end before `speechSynthesis.speak()`.
    Strips technical artefacts (snake_case, JSON, URLs, file paths) and
    expands CEFR + percent for natural read-aloud.
    """
    from core.services.text_humanizer import humanize_for_speech

    text = (request.POST.get("text") or "")[:8000]
    language = request.POST.get("language") or "en"
    if language not in ("en", "ar"):
        language = "en"
    return JsonResponse({
        "text": humanize_for_speech(text, language=language),
        "language": language,
    })
