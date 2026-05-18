from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import CEFR_CHOICES

from .models import (
    CATEGORY_CHOICES,
    Book,
    Chapter,
    ComprehensionQuestion,
    LibraryProgress,
)


@login_required
def book_list(request):
    level = (request.GET.get("level") or "").strip()
    category = (request.GET.get("category") or "").strip()

    qs = Book.objects.filter(is_published=True)
    if level:
        qs = qs.filter(level=level)
    if category:
        qs = qs.filter(category=category)

    paginator = Paginator(qs, 12)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(request, "library/list.html", {
        "page_obj": page_obj,
        "level": level,
        "category": category,
        "levels": [c[0] for c in CEFR_CHOICES],
        "categories": CATEGORY_CHOICES,
        "is_subscribed": request.user.profile.is_subscribed,
    })


@login_required
def book_detail(request, pk):
    if not request.user.profile.is_subscribed:
        messages.warning(request, "Subscribe to read from the library.")
        return redirect("subscribe")

    book = get_object_or_404(Book, pk=pk, is_published=True)

    chapter = None
    progress = None
    questions = []
    if not book.pdf:
        chapters = list(book.chapters.all())
        if not chapters:
            raise Http404("Book has no content")
        chapter_id = (request.GET.get("chapter") or "").strip()
        if chapter_id:
            chapter = next((c for c in chapters if str(c.id) == chapter_id), None)
        chapter = chapter or chapters[0]

        progress, _ = LibraryProgress.objects.get_or_create(
            user=request.user, chapter=chapter
        )
        questions = list(chapter.comprehension_questions.all())
    else:
        chapters = []

    return render(request, "library/detail.html", {
        "book": book,
        "chapters": chapters,
        "chapter": chapter,
        "progress": progress,
        "questions": questions,
    })


@login_required
@require_POST
def update_position(request, chapter_id):
    """Persist scroll/read position. Best-effort, idempotent."""
    if not request.user.profile.is_subscribed:
        return JsonResponse({"ok": False, "error": "subscription_required"}, status=403)

    chapter = get_object_or_404(Chapter, pk=chapter_id, book__is_published=True)
    try:
        position = int(request.POST.get("position") or 0)
    except (TypeError, ValueError):
        position = 0
    progress, _ = LibraryProgress.objects.get_or_create(
        user=request.user, chapter=chapter
    )
    if position > (progress.last_position or 0):
        progress.last_position = position
        progress.save(update_fields=["last_position", "updated_at"])
    return JsonResponse({"ok": True, "last_position": progress.last_position})


@login_required
@require_POST
def mark_chapter_complete(request, chapter_id):
    """Flip the chapter to completed, refresh motivation engine."""
    if not request.user.profile.is_subscribed:
        return redirect("subscribe")

    chapter = get_object_or_404(Chapter, pk=chapter_id, book__is_published=True)
    progress, _ = LibraryProgress.objects.get_or_create(
        user=request.user, chapter=chapter
    )
    if not progress.completed:
        progress.completed = True
        progress.save(update_fields=["completed", "updated_at"])

        # Best-effort motivation refresh — never blocks reading flow.
        try:
            from motivation.services.motivation_engine import run_for_user
            run_for_user(request.user)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("library: motivation engine failed")

    return redirect(f"{chapter.book.id and '/library/' or ''}{chapter.book_id}/?chapter={chapter.id}")


@login_required
def chapter_summary(request, chapter_id):
    """Return a short summary + key points for a chapter (cached after
    the first call). Free-form GET. Subscription-gated."""
    if not request.user.profile.is_subscribed:
        return JsonResponse({"ok": False, "error": "subscription_required"}, status=403)
    chapter = get_object_or_404(Chapter, pk=chapter_id, book__is_published=True)
    try:
        from library.services.summarizer import summarize_chapter
        lang = (
            getattr(getattr(request.user, "profile", None), "preferred_language", "en")
            or "en"
        )
        result = summarize_chapter(chapter, language=lang)
        return JsonResponse({"ok": True, **result})
    except Exception:
        import logging
        logging.getLogger(__name__).exception("chapter_summary failed")
        return JsonResponse({"ok": False, "error": "internal"}, status=500)


@login_required
@require_POST
def submit_comprehension(request, chapter_id):
    """Grade short comprehension answers and persist `comprehension_score`."""
    if not request.user.profile.is_subscribed:
        return JsonResponse({"ok": False, "error": "subscription_required"}, status=403)

    chapter = get_object_or_404(Chapter, pk=chapter_id, book__is_published=True)
    questions = list(chapter.comprehension_questions.all())
    if not questions:
        return JsonResponse({"ok": False, "error": "no_questions"}, status=404)

    correct = 0
    feedback = []
    for q in questions:
        user_ans = (request.POST.get(f"q_{q.id}") or "").strip()
        expected = (q.correct_answer or "").strip()
        is_correct = bool(expected) and user_ans.lower() == expected.lower()
        if is_correct:
            correct += 1
        feedback.append({
            "id": q.id,
            "question": q.question,
            "your_answer": user_ans,
            "correct_answer": expected,
            "is_correct": is_correct,
            "explanation": q.explanation or "",
        })

    score = int(round(correct * 100 / max(len(questions), 1)))
    progress, _ = LibraryProgress.objects.get_or_create(
        user=request.user, chapter=chapter
    )
    progress.comprehension_score = score
    if score >= 60 and not progress.completed:
        progress.completed = True
    progress.save(update_fields=["comprehension_score", "completed", "updated_at"])

    # Library reading + comprehension drives motivation refresh.
    try:
        from motivation.services.motivation_engine import run_for_user
        run_for_user(request.user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("library: motivation engine failed")

    return JsonResponse({
        "ok": True,
        "score": score,
        "correct": correct,
        "total": len(questions),
        "feedback": feedback,
    })


# ---------------------------------------------------------------------------
# Natural Reader (Sprint 4) — TTS-on-demand for chapter text.
#
# Pipeline: prepare → start session → synthesize chunk(s) → finish session.
# Quota deduction happens at finish-time so a chapter the user only skims
# isn't billed at the chapter level.
# ---------------------------------------------------------------------------

@login_required
def chapter_listen(request, chapter_id):
    """Read-only landing page: shows the prepared text + Listen controls.

    The actual audio is fetched via the JSON endpoints below so the user
    sees a single page with a streaming-style player.
    """
    chapter = get_object_or_404(Chapter.objects.select_related("book"), pk=chapter_id)
    from subscriptions.services import library_audio_service, preference_service, quota_service
    prepared = library_audio_service.prepare(
        chapter.body,
        language="en",
        source="library_chapter",
        source_id=chapter.pk,
        persist_log=False,  # don't spam logs on page render — only on actual listen
    )
    voice = preference_service.resolve_voice_for(request.user)
    remaining = quota_service.get_remaining_library_seconds(request.user)
    return render(request, "library/chapter_listen.html", {
        "chapter": chapter,
        "book": chapter.book,
        "prepared": prepared,
        "voice": voice,
        "remaining_seconds": remaining,
    })


@login_required
@require_POST
def chapter_audio_start(request, chapter_id):
    """Open a library audio session for this chapter."""
    chapter = get_object_or_404(Chapter.objects.select_related("book"), pk=chapter_id)
    from subscriptions.services import library_audio_service, preference_service
    from subscriptions.services.library_audio_service import (
        LibraryConcurrentSessionExists, LibraryQuotaExhausted,
    )
    voice_profile = preference_service.resolve_voice_for(request.user)
    try:
        session = library_audio_service.start_session(
            request.user,
            chapter_id=chapter.pk,
            chapter_title=chapter.title,
            voice_profile=voice_profile,
        )
    except LibraryQuotaExhausted:
        return JsonResponse(
            {
                "success": False,
                "error": "limit_reached",
                "message": "Your library audio minutes are exhausted today.",
                "upgrade_url": "/subscriptions/upgrade/",
            },
            status=402,
        )
    except LibraryConcurrentSessionExists:
        return JsonResponse(
            {
                "success": False,
                "error": "concurrent_session",
                "message": "Another listening session is already active.",
            },
            status=409,
        )
    # Prepare + persist the normalization log on first listen.
    prepared = library_audio_service.prepare(
        chapter.body,
        language="en",
        source="library_chapter",
        source_id=chapter.pk,
        persist_log=True,
    )
    return JsonResponse({
        "success": True,
        "audio_session_id": session.pk,
        "chunks": prepared["chunks"],
        "voice": voice_profile.provider_voice_id if voice_profile else "alloy",
        "estimated_seconds": prepared["estimated_seconds"],
    })


@login_required
@require_POST
def chapter_audio_chunk(request, chapter_id):
    """Synthesize a single chunk and return base64 audio.

    Requires an open session belonging to the user — the chunk text is
    sent in the request body, but only the user's open session id
    authorises the spend.
    """
    import json
    from subscriptions.services import library_audio_service
    from subscriptions.models import LibraryAudioSession
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    session_id = payload.get("audio_session_id")
    chunk_text = (payload.get("chunk") or "").strip()
    if not session_id or not chunk_text:
        return JsonResponse({"success": False, "error": "bad_request"}, status=400)
    session = LibraryAudioSession.objects.filter(
        pk=session_id, user=request.user, status="in_progress",
    ).first()
    if session is None:
        return JsonResponse({"success": False, "error": "no_open_session"}, status=409)
    voice = session.voice_profile.provider_voice_id if session.voice_profile else "alloy"
    audio = library_audio_service.synthesize_chunk(chunk_text, voice=voice, language="en")
    return JsonResponse({
        "success": True,
        "audio_b64": audio.get("audio_b64", ""),
        "format": audio.get("format", ""),
    })


@login_required
@require_POST
def chapter_audio_finish(request, chapter_id):
    """Close the session and deduct seconds."""
    import json
    from subscriptions.services import library_audio_service
    from subscriptions.models import LibraryAudioSession
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        payload = {}
    session_id = payload.get("audio_session_id")
    seconds = max(0, int(payload.get("seconds") or 0))
    killed = bool(payload.get("killed_by_quota"))
    if not session_id:
        return JsonResponse({"success": False, "error": "bad_request"}, status=400)
    session = LibraryAudioSession.objects.filter(pk=session_id).first()
    if session is None:
        return JsonResponse({"success": False, "error": "not_found"}, status=404)
    if session.user_id != request.user.id:
        return JsonResponse({"success": False, "error": "forbidden"}, status=403)
    closed = library_audio_service.end_session(
        session.pk, actual_seconds=seconds, killed_by_quota=killed,
    )
    return JsonResponse({
        "success": True,
        "seconds_consumed": closed.consumed_seconds,
        "remaining_seconds": closed.remaining_after_seconds,
    })
