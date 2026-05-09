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
