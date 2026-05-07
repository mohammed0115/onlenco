from urllib.parse import parse_qs, urlparse

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods

from .models import Lesson, LessonProgress, Quiz


def _to_embed_url(url: str) -> str:
    """Convert common YouTube watch/share URLs to embeddable URLs."""
    if not url:
        return ""
    try:
        if "youtube.com/watch" in url:
            parsed = urlparse(url)
            vid = parse_qs(parsed.query).get("v", [None])[0]
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
        if "youtu.be/" in url:
            vid = url.split("youtu.be/", 1)[1].split("?", 1)[0].split("&", 1)[0].strip("/")
            if vid:
                return f"https://www.youtube.com/embed/{vid}"
    except Exception:
        pass
    return url


@login_required
def dashboard(request):
    """Student dashboard. Shows the placement-test prompt (if not yet
    taken), the lesson grid, and a subscribe CTA when the student isn't
    on an active plan."""

    profile = request.user.profile
    qs = Lesson.objects.all()

    # If the learner has a CEFR level, surface their level + the next two
    # levels so they can see the path forward without overwhelming them.
    if profile.cefr_level:
        order = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]
        try:
            i = order.index(profile.cefr_level)
            visible = order[i:i + 3]
            qs = qs.filter(level__in=visible)
        except ValueError:
            pass

    lessons = list(qs)
    progress_map = {
        p.lesson_id: p
        for p in LessonProgress.objects.filter(user=request.user, lesson__in=lessons)
    }
    for l in lessons:
        l.progress = progress_map.get(l.id)

    next_club_event = None
    next_club_rsvp = None
    try:
        from club.models import ClubEvent, ClubRSVP

        next_club_event = (
            ClubEvent.objects.filter(is_published=True, starts_at__gte=timezone.now())
            .order_by("starts_at")
            .first()
        )
        if next_club_event:
            next_club_rsvp = (
                ClubRSVP.objects.filter(event=next_club_event, user=request.user)
                .order_by("-updated_at")
                .first()
            )
    except Exception:
        pass

    last_rejected = None
    try:
        latest = request.user.payment_submissions.order_by("-created_at").first()
        last_rejected = (
            request.user.payment_submissions
            .filter(status="rejected")
            .order_by("-created_at")
            .first()
        )
        if latest and latest.status != "rejected":
            last_rejected = None
    except Exception:
        last_rejected = None

    return render(request, "lessons/dashboard.html", {
        "profile": profile,
        "lessons": lessons,
        "is_subscribed": profile.is_subscribed,
        "next_club_event": next_club_event,
        "next_club_rsvp": next_club_rsvp,
        "last_rejected": last_rejected,
    })


@login_required
def lesson_detail(request, pk):
    lesson = get_object_or_404(Lesson, pk=pk)
    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

    quiz = None
    try:
        quiz = lesson.quiz
    except Quiz.DoesNotExist:
        quiz = None

    return render(request, "lessons/detail.html", {
        "lesson": lesson,
        "progress": progress,
        "quiz": quiz,
        "embed_url": _to_embed_url(lesson.video_url),
        "is_subscribed": request.user.profile.is_subscribed,
    })


@login_required
@require_POST
def mark_video_complete(request, pk):
    if not request.user.profile.is_subscribed:
        return HttpResponseForbidden("Subscription required")

    lesson = get_object_or_404(Lesson, pk=pk)
    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

    if not progress.video_completed:
        progress.video_completed = True
        if progress.is_complete and not progress.completed_at:
            progress.completed_at = timezone.now()
        progress.save()
        messages.success(request, "Marked as watched.")

    return redirect("lesson_detail", pk=lesson.pk)


@login_required
@require_http_methods(["GET", "POST"])
def quiz_attempt(request, pk):
    if not request.user.profile.is_subscribed:
        return HttpResponseForbidden("Subscription required")

    lesson = get_object_or_404(Lesson, pk=pk)
    progress, _ = LessonProgress.objects.get_or_create(user=request.user, lesson=lesson)

    try:
        quiz = lesson.quiz
    except Quiz.DoesNotExist:
        quiz = None

    if not quiz:
        raise Http404("Lesson has no quiz")

    questions = list(quiz.questions.all())

    def _choices(q):
        return [
            ("a", q.choice_a),
            ("b", q.choice_b),
            ("c", q.choice_c),
            ("d", q.choice_d),
        ]

    if request.method == "GET":
        return render(request, "lessons/quiz.html", {
            "lesson": lesson,
            "quiz": quiz,
            "questions": questions,
        })

    # POST: grade attempt
    correct_count = 0
    results = []
    for q in questions:
        chosen = (request.POST.get(f"q_{q.id}") or "").strip().lower()
        is_correct = chosen == q.correct
        if is_correct:
            correct_count += 1
        results.append({
            "q": q,
            "chosen": chosen,
            "correct": q.correct,
            "choices": [(k, v) for k, v in _choices(q) if v],
        })

    total = len(questions) or 1
    score = int(correct_count * 100 / total)

    progress.quiz_score = score
    progress.quiz_passed = score >= quiz.pass_score
    if progress.is_complete and not progress.completed_at:
        progress.completed_at = timezone.now()
    progress.save()

    return render(request, "lessons/quiz_result.html", {
        "lesson": lesson,
        "quiz": quiz,
        "progress": progress,
        "score": score,
        "passed": progress.quiz_passed,
        "results": results,
    })
