"""JSON endpoints driving the AI Tutor SPA.

Why these live in `tutor/api/` rather than alongside the page views:
the page view returns HTML/redirects (login_required → 302 to /auth/),
which is the wrong response for an in-page fetch() call. The DRF views
below return clean JSON with proper 401/403/400 status codes so the
front-end can branch without HTML-vs-JSON sniffing.
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import status
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.services.text_humanizer import humanize_for_speech, humanize_text
from tutor.models import TutorConversation, TutorMessage
from tutor.services import chat, chat_stream_tokens


logger = logging.getLogger(__name__)
perf_logger = logging.getLogger("tutor.perf")

MAX_MESSAGE_CHARS = 4000


@contextmanager
def _timer(step: str, *, user_id: int | None = None, extra: dict | None = None):
    """Emit `[tutor.perf] step=<name> ms=<int> user=<id> ...` to the logs.

    Use as a `with` block around any meaningful chunk of work. Lines are
    grep-friendly so an SRE can build a Grafana panel directly from
    Loki / journald without parsing JSON. The block re-raises whatever
    the wrapped code raised, after timing it.
    """
    started = time.perf_counter()
    try:
        yield
    finally:
        ms = int((time.perf_counter() - started) * 1000)
        bits = [f"step={step}", f"ms={ms}"]
        if user_id is not None:
            bits.append(f"user={user_id}")
        if extra:
            for k, v in extra.items():
                bits.append(f"{k}={v}")
        perf_logger.info("[tutor.perf] " + " ".join(bits))


def _ajax_login_required(view):
    """Auth guard that returns 401 JSON instead of a 302 redirect.

    StreamingHttpResponse can't sit behind DRF's `@api_view`, so we
    use this thin decorator on the streaming endpoint to keep the
    no-page-refresh contract intact.
    """
    from functools import wraps

    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"success": False, "error": "auth_required"},
                status=401,
            )
        return view(request, *args, **kwargs)

    return _wrapped


def _detect_lang(text: str) -> str:
    return "ar" if any("؀" <= ch <= "ۿ" for ch in (text or "")) else "en"


def _require_subscription(user):
    """Return None if the user can chat with the tutor; else an error tuple."""
    profile = getattr(user, "profile", None)
    if profile and getattr(profile, "is_subscribed", False):
        return None
    return Response(
        {"success": False, "error": "subscription_required",
         "message": "Subscribe to chat with the AI tutor."},
        status=status.HTTP_402_PAYMENT_REQUIRED,
    )


def _get_conversation_for(user, conversation_id):
    """Look up a conversation, enforce ownership, return (conv, error_response)."""
    try:
        conv = TutorConversation.objects.get(pk=conversation_id)
    except TutorConversation.DoesNotExist:
        return None, Response(
            {"success": False, "error": "not_found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if conv.user_id != user.id:
        return None, Response(
            {"success": False, "error": "forbidden"},
            status=status.HTTP_403_FORBIDDEN,
        )
    return conv, None


@extend_schema(
    request=inline_serializer(
        name="TutorChatSendRequest",
        fields={
            "message": drf_serializers.CharField(),
            "conversation_id": drf_serializers.IntegerField(required=False),
            "voice": drf_serializers.BooleanField(required=False),
            "speaking_seconds": drf_serializers.IntegerField(required=False),
        },
    ),
    responses=inline_serializer(
        name="TutorChatSendResponse",
        fields={
            "success": drf_serializers.BooleanField(),
            "conversation_id": drf_serializers.IntegerField(),
            "state": drf_serializers.CharField(),
        },
    ),
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def chat_send(request):
    """Send a text message and get the assistant's reply, in JSON.

    Mirrors `tutor.views.send_message` but never redirects — failures
    return structured JSON so the SPA can show a friendly toast.
    """
    locked = _require_subscription(request.user)
    if locked is not None:
        return locked

    payload = request.data or {}
    text = (payload.get("message") or "").strip()
    conversation_id = payload.get("conversation_id")
    voice = bool(payload.get("voice"))

    if not text:
        return Response(
            {"success": False, "error": "empty_message"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    text = text[:MAX_MESSAGE_CHARS]

    if conversation_id is None:
        conv = TutorConversation.objects.create(user=request.user)
    else:
        conv, err = _get_conversation_for(request.user, conversation_id)
        if err is not None:
            return err

    user_msg = TutorMessage.objects.create(
        conversation=conv, role="user", content=text,
    )
    if not conv.title:
        conv.title = " ".join(text.split()[:8])[:200]
        conv.save(update_fields=["title"])

    try:
        reply = chat(conv, text, voice=voice)
    except Exception:
        logger.exception("Tutor chat call crashed")
        return Response(
            {"success": False, "error": "ai_unavailable",
             "message": "The AI tutor is temporarily unavailable. Try again in a moment."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    ai_msg = TutorMessage.objects.create(
        conversation=conv, role="assistant", content=reply,
    )

    try:
        from motivation.services import activity_collector
        snap = activity_collector.collect_daily_activity(request.user)
        snap.writing_attempts = (snap.writing_attempts or 0) + 1
        speaking_seconds = max(0, min(int(payload.get("speaking_seconds") or 0), 3600))
        if speaking_seconds > 0:
            snap.speaking_minutes = (snap.speaking_minutes or 0) + max(1, speaking_seconds // 60)
        snap.save(update_fields=["writing_attempts", "speaking_minutes", "updated_at"])
    except Exception:
        logger.exception("Tutor SPA: activity credit failed")
    try:
        from motivation.services.motivation_engine import run_for_user
        run_for_user(request.user)
    except Exception:
        logger.exception("Tutor SPA: motivation engine failed")

    return Response({
        "success": True,
        "conversation_id": conv.id,
        "user_message": {
            "id": user_msg.id,
            "content": text,
            "created_at": user_msg.created_at.isoformat(),
        },
        "ai_message": {
            "id": ai_msg.id,
            "content": reply,
            "content_humanized": humanize_text(reply, language=_detect_lang(reply)),
            "speech_text": humanize_for_speech(reply, language=_detect_lang(reply)),
            "created_at": ai_msg.created_at.isoformat(),
        },
        "state": "completed",
    })


@extend_schema(
    request={
        "multipart/form-data": {
            "type": "object",
            "properties": {"audio": {"type": "string", "format": "binary"}},
            "required": ["audio"],
        }
    },
    responses=inline_serializer(
        name="TutorVoiceTranscribeResponse",
        fields={
            "success": drf_serializers.BooleanField(),
            "attempt_id": drf_serializers.IntegerField(required=False),
            "transcript": drf_serializers.CharField(allow_blank=True),
            "duration_seconds": drf_serializers.IntegerField(),
        },
    ),
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def voice_transcribe(request):
    """Receive a recorded audio blob and return its transcript.

    Validates mime + size (10 MB cap) before handing to Whisper. Saves a
    `SpeakingAttempt` row so the result is auditable.
    """
    user_id = getattr(request.user, "id", None)
    started_total = time.perf_counter()

    audio = request.FILES.get("audio")
    if audio is None:
        return Response(
            {"success": False, "error": "no_audio"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    with _timer("audio_validate", user_id=user_id):
        from speech.services.audio_validation import validate_audio_upload
        err = validate_audio_upload(audio)
    if err is not None:
        return Response(
            {"success": False, "error": err["code"], "message": err["message"]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from placement.services.stt import transcribe
    try:
        with _timer("stt", user_id=user_id, extra={"size": getattr(audio, "size", 0)}):
            result = transcribe(audio)
    except Exception:
        logger.exception("Tutor STT failed")
        return Response(
            {"success": False, "error": "stt_unavailable",
             "message": "Couldn't transcribe your audio. Try again."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    transcript = (result.get("transcript") or "").strip()
    duration = int(result.get("duration_seconds") or 0)

    # Persist a lightweight SpeakingAttempt row WITHOUT the audio file so
    # the response can return immediately. Slow storage backends (S3 with
    # retries, network FS) were taking many seconds on `audio_file=audio`,
    # which blocked the transcript and made the whole voice path feel
    # unresponsive (users reported multi-minute waits before the bubble
    # appeared). The audio bytes are read once here and written from a
    # daemon thread so the request can return in <100 ms after STT.
    with _timer("attempt_save", user_id=user_id):
        from speech.models import SpeakingAttempt
        attempt = SpeakingAttempt.objects.create(
            user=request.user,
            transcript=transcript,
            duration_seconds=duration,
            confidence=float(result.get("confidence") or 0.0),
            source="tutor",
        )

    try:
        audio.seek(0)
        audio_bytes = audio.read()
        audio_name = getattr(audio, "name", "recording.webm") or "recording.webm"
    except Exception:
        audio_bytes, audio_name = b"", "recording.webm"

    if audio_bytes:
        import threading
        from django.core.files.base import ContentFile

        def _persist_audio(att_id: int, name: str, blob: bytes) -> None:
            try:
                from speech.models import SpeakingAttempt as _SA
                row = _SA.objects.filter(id=att_id).first()
                if row is None:
                    return
                row.audio_file.save(name, ContentFile(blob), save=True)
            except Exception:
                logger.exception("Tutor: deferred audio save failed for attempt %s", att_id)

        threading.Thread(
            target=_persist_audio,
            args=(attempt.id, audio_name, audio_bytes),
            name="tutor-audio-persist",
            daemon=True,
        ).start()

    perf_logger.info(
        "[tutor.perf] step=transcribe_total ms=%d user=%s chars=%d",
        int((time.perf_counter() - started_total) * 1000),
        user_id, len(transcript),
    )

    if not transcript:
        return Response({
            "success": True,
            "attempt_id": attempt.id,
            "transcript": "",
            "duration_seconds": duration,
            "message": "I didn't catch that — could you try again?",
        })

    return Response({
        "success": True,
        "attempt_id": attempt.id,
        "transcript": transcript,
        "duration_seconds": duration,
    })


@require_POST
@_ajax_login_required
@csrf_protect
def voice_respond_stream(request):
    """Streaming variant of voice_respond — typewriter SSE response.

    Same shape as `chat_stream` but the input is a transcript already
    produced by `voice_transcribe`, plus a `speaking_seconds` counter
    used for activity stats. Returns SSE so the assistant bubble paints
    word-by-word as the AI generates, instead of waiting for the full
    reply.
    """
    profile = getattr(request.user, "profile", None)
    if not (profile and getattr(profile, "is_subscribed", False)):
        return JsonResponse(
            {"success": False, "error": "subscription_required"},
            status=402,
        )
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "bad_json"}, status=400)

    transcript = (payload.get("transcript") or "").strip()
    if not transcript:
        return JsonResponse({"success": False, "error": "empty_transcript"}, status=400)
    transcript = transcript[:MAX_MESSAGE_CHARS]
    conversation_id = payload.get("conversation_id")

    if conversation_id is None:
        conv = TutorConversation.objects.create(user=request.user)
    else:
        try:
            conv = TutorConversation.objects.get(pk=conversation_id)
        except TutorConversation.DoesNotExist:
            return JsonResponse({"success": False, "error": "not_found"}, status=404)
        if conv.user_id != request.user.id:
            return JsonResponse({"success": False, "error": "forbidden"}, status=403)

    user_msg = TutorMessage.objects.create(
        conversation=conv, role="user", content=transcript,
    )
    if not conv.title:
        conv.title = " ".join(transcript.split()[:8])[:200]
        conv.save(update_fields=["title"])
    ai_msg = TutorMessage.objects.create(
        conversation=conv, role="assistant", content="",
    )

    # Activity stats (cheap, sync) — speaking_seconds + writing_attempts
    try:
        speaking_seconds = max(0, min(int(payload.get("speaking_seconds") or 0), 3600))
        from motivation.services import activity_collector
        snap = activity_collector.collect_daily_activity(request.user)
        if speaking_seconds > 0:
            snap.speaking_minutes = (snap.speaking_minutes or 0) + max(1, speaking_seconds // 60)
        snap.writing_attempts = (snap.writing_attempts or 0) + 1
        snap.save(update_fields=["speaking_minutes", "writing_attempts", "updated_at"])
    except Exception:
        logger.exception("voice_respond_stream: activity stats failed")

    response = StreamingHttpResponse(
        _live_stream_response(
            conv, transcript, voice=True,
            user_msg_id=user_msg.id, ai_msg_id=ai_msg.id,
            request_user=request.user,
        ),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


@extend_schema(
    request=inline_serializer(
        name="TutorVoiceRespondRequest",
        fields={
            "transcript": drf_serializers.CharField(),
            "conversation_id": drf_serializers.IntegerField(required=False),
            "speaking_seconds": drf_serializers.IntegerField(required=False),
        },
    ),
    responses=inline_serializer(
        name="TutorVoiceRespondResponse",
        fields={
            "success": drf_serializers.BooleanField(),
            "conversation_id": drf_serializers.IntegerField(),
            "state": drf_serializers.CharField(),
        },
    ),
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def voice_respond(request):
    """Take a transcript, run the tutor pipeline, return the AI reply.

    Separated from `chat_send` so the SPA can show the transcript to the
    user before the AI reply finishes (better-feeling UX).
    """
    locked = _require_subscription(request.user)
    if locked is not None:
        return locked

    payload = request.data or {}
    transcript = (payload.get("transcript") or "").strip()
    if not transcript:
        return Response(
            {"success": False, "error": "empty_transcript"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    transcript = transcript[:MAX_MESSAGE_CHARS]
    conversation_id = payload.get("conversation_id")

    if conversation_id is None:
        conv = TutorConversation.objects.create(user=request.user)
    else:
        conv, err = _get_conversation_for(request.user, conversation_id)
        if err is not None:
            return err

    user_msg = TutorMessage.objects.create(
        conversation=conv, role="user", content=transcript,
    )
    if not conv.title:
        conv.title = " ".join(transcript.split()[:8])[:200]
        conv.save(update_fields=["title"])

    try:
        reply = chat(conv, transcript, voice=True)
    except Exception:
        logger.exception("Tutor voice respond crashed")
        return Response(
            {"success": False, "error": "ai_unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    ai_msg = TutorMessage.objects.create(
        conversation=conv, role="assistant", content=reply,
    )

    try:
        speaking_seconds = max(0, min(int(payload.get("speaking_seconds") or 0), 3600))
        from motivation.services import activity_collector
        snap = activity_collector.collect_daily_activity(request.user)
        if speaking_seconds > 0:
            snap.speaking_minutes = (snap.speaking_minutes or 0) + max(1, speaking_seconds // 60)
        snap.writing_attempts = (snap.writing_attempts or 0) + 1
        snap.save(update_fields=["speaking_minutes", "writing_attempts", "updated_at"])
        from motivation.services.motivation_engine import run_for_user
        run_for_user(request.user)
    except Exception:
        logger.exception("Tutor voice respond: activity/motivation hook failed")

    lang = _detect_lang(reply)
    return Response({
        "success": True,
        "conversation_id": conv.id,
        "user_message": {
            "id": user_msg.id, "content": transcript,
            "created_at": user_msg.created_at.isoformat(),
        },
        "ai_message": {
            "id": ai_msg.id,
            "content": reply,
            "content_humanized": humanize_text(reply, language=lang),
            "speech_text": humanize_for_speech(reply, language=lang),
            "language": lang,
            "created_at": ai_msg.created_at.isoformat(),
        },
        "state": "completed",
    })


@extend_schema(
    responses=inline_serializer(
        name="TutorVoiceHistoryResponse",
        fields={
            "success": drf_serializers.BooleanField(),
            "count": drf_serializers.IntegerField(required=False),
            "deleted": drf_serializers.IntegerField(required=False),
        },
    ),
)
@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def voice_history(request):
    """Privacy controls: list or delete the user's saved voice recordings.

    GET   → list of `SpeakingAttempt` rows belonging to the request user
            (id, transcript, duration, source, created_at, has_audio).
    DELETE → delete the audio_file on every row; transcripts are kept
            so the learning-error history isn't lost. Mirrors a "delete
            my voice history" button shown in the Tutor UI.
    """
    from speech.models import SpeakingAttempt

    qs = SpeakingAttempt.objects.filter(user=request.user).order_by("-created_at")

    if request.method == "DELETE":
        deleted = 0
        for att in qs.iterator():
            try:
                if att.audio_file:
                    att.audio_file.delete(save=False)
                    att.audio_file = None
                    att.save(update_fields=["audio_file"])
                    deleted += 1
            except Exception:
                logger.exception("Voice history delete failed for id=%s", att.id)
        return Response({"success": True, "deleted": deleted})

    items = [
        {
            "id": a.id,
            "transcript": a.transcript[:200],
            "duration_seconds": a.duration_seconds,
            "source": a.source,
            "has_audio": bool(a.audio_file),
            "created_at": a.created_at.isoformat(),
        }
        for a in qs[:200]
    ]
    return Response({"success": True, "count": len(items), "items": items})


def _sse(event: dict) -> bytes:
    """Format one Server-Sent Event payload."""
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode("utf-8")


def _live_stream_response(conversation, user_message, *, voice,
                          user_msg_id, ai_msg_id, request_user):
    """Generator that drives the SSE response.

    Real token-by-token streaming from the upstream AI provider. We
    open the upstream HTTP request, forward each delta as a `token`
    SSE event, accumulate the full reply, and persist it to the
    `TutorMessage` row at the end. The user sees the first word in
    ~300 ms instead of after the full 5–8 s round-trip.
    """
    user_id = getattr(request_user, "id", None)
    started_total = time.perf_counter()
    first_token_ms = None

    yield _sse({
        "type": "start",
        "user_message_id": user_msg_id,
        "ai_message_id": ai_msg_id,
        "conversation_id": conversation.id,
        "language": "auto",
    })

    parts = []
    stream_started = time.perf_counter()
    try:
        for token in chat_stream_tokens(conversation, user_message, voice=voice):
            if first_token_ms is None:
                first_token_ms = int((time.perf_counter() - stream_started) * 1000)
                perf_logger.info(
                    "[tutor.perf] step=chat_first_token ms=%d user=%s voice=%s",
                    first_token_ms, user_id, voice,
                )
            parts.append(token)
            yield _sse({"type": "token", "token": token})
    except Exception:
        logger.exception("chat_stream generator crashed")
        yield _sse({"type": "error", "error": "ai_unavailable"})
        return

    perf_logger.info(
        "[tutor.perf] step=chat_stream_total ms=%d user=%s voice=%s tokens=%d",
        int((time.perf_counter() - stream_started) * 1000),
        user_id, voice, len(parts),
    )

    full = "".join(parts).strip() or "Could you say a bit more?"
    lang = _detect_lang(full)

    # Persist the assistant message AFTER streaming completes — this is
    # the canonical record. The token events were transient.
    try:
        with _timer("persist_reply", user_id=user_id):
            TutorMessage.objects.filter(pk=ai_msg_id).update(content=full)
    except Exception:
        logger.exception("chat_stream: failed to persist final reply")

    # Activity stats (cheap, sync) + motivation engine (heavier; backgrounded).
    try:
        with _timer("activity_stats", user_id=user_id):
            from motivation.services import activity_collector
            snap = activity_collector.collect_daily_activity(request_user)
            snap.writing_attempts = (snap.writing_attempts or 0) + 1
            snap.save(update_fields=["writing_attempts", "updated_at"])
    except Exception:
        logger.exception("chat_stream: activity stats failed")

    # Backgrounded — motivation_engine.run_for_user can take 100ms-2s+
    # depending on how many achievements/messages it generates. Letting
    # it block the SSE close adds tail latency for no UX benefit.
    try:
        from tutor.services._chat import fire_motivation_hook
        fire_motivation_hook(request_user)
    except Exception:
        logger.exception("chat_stream: motivation fire failed")

    yield _sse({
        "type": "done",
        "content": full,
        "content_humanized": humanize_text(full, language=lang),
        "speech_text": humanize_for_speech(full, language=lang),
        "language": lang,
    })

    perf_logger.info(
        "[tutor.perf] step=stream_view_total ms=%d user=%s voice=%s first_token_ms=%s",
        int((time.perf_counter() - started_total) * 1000),
        user_id, voice, first_token_ms,
    )


@require_POST
@_ajax_login_required
@csrf_protect
def chat_stream(request):
    """Streaming variant of chat_send — typewriter SSE response.

    Same contract as chat_send (subscription gate, ownership, message
    persistence, motivation hooks) but emits Server-Sent Events so the
    front-end can paint tokens as they arrive instead of waiting for
    the full reply.
    """
    profile = getattr(request.user, "profile", None)
    if not (profile and getattr(profile, "is_subscribed", False)):
        return JsonResponse(
            {"success": False, "error": "subscription_required"},
            status=402,
        )

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "bad_json"}, status=400)

    text = (payload.get("message") or "").strip()
    if not text:
        return JsonResponse({"success": False, "error": "empty_message"}, status=400)
    text = text[:MAX_MESSAGE_CHARS]
    voice = bool(payload.get("voice"))
    conversation_id = payload.get("conversation_id")

    if conversation_id is None:
        conv = TutorConversation.objects.create(user=request.user)
    else:
        try:
            conv = TutorConversation.objects.get(pk=conversation_id)
        except TutorConversation.DoesNotExist:
            return JsonResponse({"success": False, "error": "not_found"}, status=404)
        if conv.user_id != request.user.id:
            return JsonResponse({"success": False, "error": "forbidden"}, status=403)

    user_msg = TutorMessage.objects.create(
        conversation=conv, role="user", content=text,
    )
    if not conv.title:
        conv.title = " ".join(text.split()[:8])[:200]
        conv.save(update_fields=["title"])

    # Pre-create the assistant row so the SSE generator has an id to
    # update with the final text once the stream completes. Empty
    # content for now; gets filled in `_live_stream_response`.
    ai_msg = TutorMessage.objects.create(
        conversation=conv, role="assistant", content="",
    )

    response = StreamingHttpResponse(
        _live_stream_response(
            conv, text, voice=voice,
            user_msg_id=user_msg.id, ai_msg_id=ai_msg.id,
            request_user=request.user,
        ),
        content_type="text/event-stream",
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # disable nginx buffering
    return response


@extend_schema(
    request=inline_serializer(
        name="TutorVoiceTTSRequest",
        fields={
            "text": drf_serializers.CharField(),
            "language": drf_serializers.CharField(required=False),
        },
    ),
    responses=inline_serializer(
        name="TutorVoiceTTSResponse",
        fields={
            "success": drf_serializers.BooleanField(),
            "audio_b64": drf_serializers.CharField(allow_blank=True),
            "format": drf_serializers.CharField(allow_blank=True),
            "language": drf_serializers.CharField(),
            "speech_text": drf_serializers.CharField(),
        },
    ),
)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def voice_tts(request):
    """Synthesize speech-safe text to MP3 (server-side TTS, opt-in).

    The browser's `speechSynthesis` is the default everywhere; this
    endpoint exists so we can swap to a higher-quality voice when we
    decide to spend tokens. Always pass the input through
    `humanize_for_speech` first.
    """
    payload = request.data or {}
    text = (payload.get("text") or "")[:3000]
    language = payload.get("language") or _detect_lang(text)
    if language not in ("en", "ar"):
        language = "en"
    if not text.strip():
        return Response(
            {"success": False, "error": "empty_text"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    cleaned = humanize_for_speech(text, language=language)
    from tutor.services.tts import synthesize
    try:
        result = synthesize(cleaned)
    except Exception:
        logger.exception("Tutor TTS crashed")
        return Response(
            {"success": False, "error": "tts_unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response({
        "success": True,
        "audio_b64": result.get("audio_b64", ""),
        "format": result.get("format", ""),
        "language": language,
        "speech_text": cleaned,
    })


# ---------------------------------------------------------------------------
# Realtime voice-call (OpenAI Realtime API)
# ---------------------------------------------------------------------------

@extend_schema(exclude=True)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def voice_call_session(request):
    """Mint an ephemeral OpenAI Realtime client_secret for the browser.

    Sprint 2 changes:
      * Quota is read from subscriptions (subscription → trial fallback).
      * We open a server-side ``AITutorSession`` row BEFORE issuing the
        ephemeral token, enforcing the partial-unique constraint so a
        user can't run two parallel calls by refreshing the page.
    """
    from django.conf import settings as dj_settings
    from subscriptions.services import preference_service, quota_service, session_service
    from subscriptions.services.session_service import (
        ConcurrentSessionExists, QuotaExhausted,
    )
    from tutor.services.realtime_session import (
        build_voice_system_prompt,
        request_ephemeral_session,
    )

    conversation_id = request.data.get("conversation_id")
    conv = None
    if conversation_id:
        conv, err = _get_conversation_for(request.user, conversation_id)
        if err is not None:
            return err

    # Placement-test voice call is free of the daily quota — a new
    # student takes it during onboarding before any subscription
    # exists. Trust the flag only when the conversation is actually
    # linked to a placement attempt owned by this user.
    is_placement_call = False
    if conv is not None:
        from placement.models import PlacementAttempt
        is_placement_call = PlacementAttempt.objects.filter(
            user=request.user, voice_conversation_id=conv.pk,
        ).exists()

    seconds_remaining, source_bucket = quota_service.effective_ai_tutor_remaining(request.user)
    if is_placement_call:
        # The placement call is its own short assessment, capped by
        # AI_REALTIME_MAX_SESSION_SECONDS. Give it that budget so the
        # max_session_seconds calc below works without touching quota.
        seconds_remaining = int(
            getattr(dj_settings, "AI_REALTIME_MAX_SESSION_SECONDS", 300)
        )
    elif seconds_remaining <= 0:
        return Response(
            {
                "success": False, "error": "limit_reached",
                "message": "Your AI Tutor minutes are exhausted. Upgrade your plan to continue.",
                "upgrade_url": "/subscriptions/upgrade/",
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )

    # Resolve the user's preferred voice + avatar (Sprint 3). The client
    # may override the voice for this single session by passing ``voice``
    # in the payload — we only honour known provider IDs.
    voice_profile = preference_service.resolve_voice_for(request.user)
    avatar_profile = preference_service.resolve_avatar_for(request.user)

    voice = request.data.get("voice")
    if not voice and voice_profile is not None:
        voice = voice_profile.provider_voice_id
    if not voice:
        voice = getattr(dj_settings, "AI_REALTIME_VOICE", "alloy")
    if not isinstance(voice, str) or len(voice) > 32:
        voice = "alloy"

    try:
        tutor_session = session_service.start_session(
            request.user,
            source="voice_call",
            voice=voice,
            conversation_id=conv.pk if conv else None,
            voice_profile=voice_profile,
            avatar_profile=avatar_profile,
            skip_quota=is_placement_call,
        )
    except QuotaExhausted:
        return Response(
            {
                "success": False, "error": "limit_reached",
                "message": "Your AI Tutor minutes are exhausted. Upgrade your plan to continue.",
                "upgrade_url": "/subscriptions/upgrade/",
            },
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )
    except ConcurrentSessionExists:
        return Response(
            {
                "success": False, "error": "concurrent_session",
                "message": "Another AI Tutor session is already active in another tab. Please end it first.",
            },
            status=status.HTTP_409_CONFLICT,
        )

    prompt = build_voice_system_prompt(request.user, conv)
    try:
        with _timer("realtime_session", user_id=request.user.id):
            session = request_ephemeral_session(system_prompt=prompt, voice=voice)
    except Exception:
        logger.exception("Tutor realtime session request failed")
        session_service.cancel_session(tutor_session.pk)
        return Response(
            {"success": False, "error": "ai_unavailable",
             "message": "Voice tutor is temporarily unavailable. Please try the chat instead."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if session is None:
        session_service.cancel_session(tutor_session.pk)
        return Response(
            {"success": False, "error": "ai_unavailable",
             "message": "Voice tutor is not configured."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    client_secret = (session.get("client_secret") or {}).get("value")
    if not client_secret:
        logger.error("Tutor realtime: no client_secret in upstream response")
        session_service.cancel_session(tutor_session.pk)
        return Response(
            {"success": False, "error": "ai_unavailable"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # Record the realtime session authorisation in ai_usage (Prompt 12A.1).
    # The realtime API bills browser↔OpenAI, so tokens/cost are invisible
    # here — minutes are charged on hang-up via session_service.end_session.
    try:
        from ai_usage import constants as _AC
        from ai_usage.services import ai_client as _ai_client
        _ai_client.log_realtime_session_start(
            user=request.user, role=_AC.ROLE_STUDENT,
            session_id=f"tutor_session:{tutor_session.pk}",
            metadata={"is_placement_call": bool(is_placement_call),
                      "quota_source": source_bucket},
        )
    except Exception:
        logger.warning("ai_usage realtime session-start log failed", exc_info=True)

    # The browser must cap its own session at min(provider_expiry, our quota).
    max_session_seconds = min(
        int(getattr(dj_settings, "AI_REALTIME_MAX_SESSION_SECONDS", 900)),
        seconds_remaining,
    )
    return Response({
        "success": True,
        "client_secret": client_secret,
        "session_id": session.get("id"),
        "tutor_session_id": tutor_session.pk,  # NEW — pass back to /voice/log
        "quota_source": source_bucket,
        "expires_at": session.get("expires_at"),
        "model": getattr(dj_settings, "AI_REALTIME_MODEL", ""),
        "voice": voice,
        "voice_profile": {
            "code": voice_profile.code,
            "name_en": voice_profile.name_en,
            "name_ar": voice_profile.name_ar,
            "style": voice_profile.style,
            "tone": voice_profile.tone,
        } if voice_profile else None,
        "avatar": {
            "code": avatar_profile.code,
            "name_en": avatar_profile.name_en,
            "name_ar": avatar_profile.name_ar,
            "image_url": avatar_profile.image_url,
            "lipsync_video_url": avatar_profile.lipsync_video_url,
        } if avatar_profile else None,
        "max_session_seconds": max_session_seconds,
        "minutes_remaining": seconds_remaining // 60,
        "seconds_remaining": seconds_remaining,
        "language": getattr(getattr(request.user, "profile", None), "preferred_language", "en"),
    })


@extend_schema(exclude=True)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def voice_call_log(request):
    """Record a finished voice-call session and close the AITutorSession row.

    Browser POSTs ``{seconds, transcript[], tutor_session_id?, killed_by_quota?}``
    after the user hangs up. We:
      * Close the AITutorSession row (deducts seconds from subscription
        OR free trial in the SAME bucket the session was opened against).
      * Persist spoken turns as TutorMessage rows.
      * Credit speaking-minutes on today's activity snapshot.
    """
    from subscriptions.models import AITutorSession
    from subscriptions.services import quota_service, session_service

    try:
        seconds = max(0, min(int(request.data.get("seconds") or 0), 24 * 60 * 60))
    except (TypeError, ValueError):
        seconds = 0

    conversation_id = request.data.get("conversation_id")
    conv = None
    if conversation_id:
        conv, err = _get_conversation_for(request.user, conversation_id)
        if err is not None:
            return err

    transcript = request.data.get("transcript") or []
    if not isinstance(transcript, list):
        transcript = []

    if conv is not None:
        for turn in transcript[:50]:        # cap so a misbehaving client can't spam
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            content = (turn.get("content") or "").strip()[:MAX_MESSAGE_CHARS]
            if role not in ("user", "assistant") or not content:
                continue
            TutorMessage.objects.create(
                conversation=conv, role=role, content=content,
            )
        if transcript and not conv.title:
            first_user = next(
                (t.get("content", "") for t in transcript if t.get("role") == "user"),
                "",
            )
            if first_user:
                conv.title = " ".join(first_user.split()[:8])[:200]
                conv.save(update_fields=["title"])

    # Close the open tutor session — prefer the id the browser echoes
    # back; fall back to the user's currently-open session (handles old
    # clients that don't yet send tutor_session_id).
    tutor_session_id = request.data.get("tutor_session_id")
    open_session = None
    if tutor_session_id:
        open_session = AITutorSession.objects.filter(
            pk=tutor_session_id, user=request.user,
        ).first()
    if open_session is None:
        open_session = session_service.get_open_session(request.user)

    killed_by_quota = bool(request.data.get("killed_by_quota"))
    if open_session is not None:
        closed = session_service.end_session(
            open_session.pk,
            actual_seconds=seconds,
            killed_by_quota=killed_by_quota,
        )
        remaining_after = closed.remaining_after_seconds
        quota_source = closed.quota_source
    else:
        # No matching open session (race / old client). Still deduct so we
        # don't leak free minutes.
        if seconds > 0:
            remaining_after, quota_source = quota_service.deduct_session_seconds(
                request.user, seconds,
            )
        else:
            remaining_after, quota_source = quota_service.effective_ai_tutor_remaining(request.user)

    # Credit speaking-minutes for today's activity snapshot.
    if seconds > 0:
        try:
            from motivation.services import activity_collector
            snap = activity_collector.collect_daily_activity(request.user)
            snap.speaking_minutes = (snap.speaking_minutes or 0) + max(1, seconds // 60)
            snap.save(update_fields=["speaking_minutes", "updated_at"])
        except Exception:
            logger.exception("Tutor realtime: activity credit failed")

    # End-of-call evaluation: score the user side of the transcript so
    # we have CEFR + sub-scores for placement and the conversation
    # detail page. Best-effort — failures are swallowed so they never
    # block the hangup response or leak a 500 to the browser.
    if conv is not None:
        try:
            from tutor.services.evaluation_service import evaluate_voice_call
            evaluate_voice_call(conv, seconds=seconds)
        except Exception:
            logger.exception("Tutor realtime: voice-call evaluation failed")

    return Response({
        "success": True,
        "logged_seconds": seconds,
        "seconds_remaining": remaining_after,
        "quota_source": quota_source,
    })


@extend_schema(exclude=True)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def voice_call_cancel_stale(request):
    """Recover-from-crash endpoint: cancel the caller's open voice session.

    The browser hits this when ``voice_call_session`` returned 409
    (concurrent_session) — usually because a previous call's tab was
    closed without the hang-up POST firing.
    """
    from subscriptions.services.session_service import cancel_open_session_for
    closed = cancel_open_session_for(request.user)
    return Response({"success": True, "cancelled": closed})


@extend_schema(exclude=True)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def voice_call_sdp_relay(request):
    """Server-side SDP exchange with OpenAI Realtime.

    Browsers used to POST SDP directly to ``api.openai.com/v1/realtime``
    but the GA migration tightened CORS preflights enough that some
    networks (and CSP-strict pages) now see opaque failures. Routing
    the SDP through Django:
      * keeps the ek_ token server-side (security win)
      * surfaces upstream errors in our logs instead of silent browser
        ``ai_unavailable`` messages
      * sidesteps CORS / browser-extension interference

    Body:
        {
          "client_secret": "ek_...",         # from /voice-call/session/
          "model":         "gpt-4o-...",     # echoed from the session
          "sdp":           "v=0\r\n..."      # the browser's SDP offer
        }

    Returns the SDP answer as ``text/plain`` (matching OpenAI's response
    Content-Type) so the browser can hand it straight to
    ``setRemoteDescription``.
    """
    import requests as _requests
    from django.conf import settings as _settings
    from django.http import HttpResponse

    payload = request.data or {}
    ek = (payload.get("client_secret") or "").strip()
    model = (payload.get("model") or getattr(_settings, "AI_REALTIME_MODEL", "")).strip()
    sdp = payload.get("sdp") or ""
    if not ek or not sdp:
        return Response(
            {"success": False, "error": "bad_request",
             "message": "client_secret and sdp are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # GA Realtime SDP endpoint. The old Beta path ``/v1/realtime?model=...``
    # returns 400 ``beta_api_shape_disabled`` since the GA migration —
    # the new endpoint is ``/v1/realtime/calls`` (model is implicit in
    # the ek_ session, so no query param needed).
    base = _settings.AI_API_BASE.rstrip("/")
    url = f"{base}/realtime/calls"
    try:
        upstream = _requests.post(
            url,
            data=sdp,
            headers={
                "Authorization": f"Bearer {ek}",
                "Content-Type": "application/sdp",
            },
            timeout=15,
        )
    except Exception:
        logger.exception("voice_call_sdp_relay: upstream request failed")
        return Response(
            {"success": False, "error": "ai_unavailable",
             "message": "Could not reach the voice tutor. Please try again."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not upstream.ok:
        logger.error(
            "voice_call_sdp_relay: OpenAI SDP %s — body=%s",
            upstream.status_code, upstream.text[:600],
        )
        return Response(
            {"success": False, "error": "ai_unavailable",
             "message": f"Voice tutor handshake failed ({upstream.status_code}).",
             "upstream_status": upstream.status_code,
             "upstream_body": upstream.text[:600]},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return HttpResponse(
        upstream.content,
        content_type=upstream.headers.get("Content-Type", "application/sdp"),
    )
