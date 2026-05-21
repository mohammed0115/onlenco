from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import subscription_required

from .models import CourseLessonProgress
from .services.a0_world import build_a0_world, is_a0_course
from .services.student_flow import (
    can_access_course,
    ensure_course_enrollment,
    published_course_queryset,
    published_lesson_queryset,
)


@login_required
def course_detail(request, pk):
    course = get_object_or_404(published_course_queryset(), pk=pk)
    has_access = can_access_course(request.user, course)
    enrollment = ensure_course_enrollment(request.user, course) if has_access else None
    lessons = list(published_lesson_queryset().filter(course=course))
    is_a0_world = is_a0_course(course)
    a0_world = (
        build_a0_world(course=course, lessons=lessons, user=request.user, has_access=has_access)
        if is_a0_world else None
    )

    return render(request, "courses/detail.html", {
        "course": course,
        "lessons": lessons,
        "has_access": has_access,
        "enrollment": enrollment,
        "is_a0_world": is_a0_world,
        "a0_world": a0_world,
    })


@login_required
def course_lesson_detail(request, course_pk, lesson_pk):
    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    if not can_access_course(request.user, course):
        return HttpResponseForbidden(_("An active subscription is required for this course."))

    enrollment = ensure_course_enrollment(request.user, course)
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course),
        pk=lesson_pk,
    )
    progress, _created = CourseLessonProgress.objects.get_or_create(
        user=request.user, lesson=lesson,
    )

    quiz = None
    try:
        quiz = lesson.quiz
    except Exception:
        quiz = None

    return render(request, "courses/lesson_detail.html", {
        "course": course,
        "lesson": lesson,
        "enrollment": enrollment,
        "video": lesson.get_video_embed(),
        "progress": progress,
        "quiz": quiz,
    })


@login_required
@require_POST
@subscription_required(allow_free_tier=True)
def mark_lesson_complete(request, course_pk, lesson_pk):
    """Mark a courses-app lesson's video as watched.

    Fires the motivation engine inline so XP / streak / achievements
    update without waiting for the nightly cron.
    """
    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    if not can_access_course(request.user, course):
        return HttpResponseForbidden(_("An active subscription is required for this course."))
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course),
        pk=lesson_pk,
    )
    progress, _created = CourseLessonProgress.objects.get_or_create(
        user=request.user, lesson=lesson,
    )
    if not progress.video_completed:
        progress.video_completed = True
        if progress.is_complete and not progress.completed_at:
            progress.completed_at = timezone.now()
        progress.save()
        messages.success(request, _("Marked as watched."))

    try:
        from motivation.services.motivation_engine import run_for_user
        run_for_user(request.user)
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "motivation engine post-video failed", exc_info=True
        )

    return redirect("courses:lesson_detail", course_pk=course.pk, lesson_pk=lesson.pk)


@login_required
@require_http_methods(["GET", "POST"])
@subscription_required(allow_free_tier=True)
def lesson_quiz_attempt(request, course_pk, lesson_pk):
    """Sit and grade the lesson's quiz; mirrors lessons.quiz_attempt
    for the courses-app schema."""
    course = get_object_or_404(published_course_queryset(), pk=course_pk)
    if not can_access_course(request.user, course):
        return HttpResponseForbidden(_("An active subscription is required for this course."))
    lesson = get_object_or_404(
        published_lesson_queryset().filter(course=course),
        pk=lesson_pk,
    )
    try:
        quiz = lesson.quiz
    except Exception:
        raise Http404("Lesson has no quiz")
    if quiz is None or not quiz.is_active:
        raise Http404("Lesson has no active quiz")
    questions = list(quiz.questions.all().order_by("order", "id"))

    if request.method == "GET":
        return render(request, "courses/lesson_quiz.html", {
            "course": course,
            "lesson": lesson,
            "quiz": quiz,
            "questions": questions,
        })

    # POST
    correct_count = 0
    results = []
    for q in questions:
        chosen = (request.POST.get(f"q_{q.id}") or "").strip()
        correct = (q.correct_answer or "").strip()
        is_correct = chosen.lower() == correct.lower() and bool(correct)
        if is_correct:
            correct_count += 1
        results.append({
            "q": q, "chosen": chosen,
            "correct": correct, "is_correct": is_correct,
        })
    total = len(questions) or 1
    score = int(correct_count * 100 / total)
    progress, _created = CourseLessonProgress.objects.get_or_create(
        user=request.user, lesson=lesson,
    )
    progress.quiz_score = score
    progress.quiz_passed = score >= int(quiz.passing_score or 70)
    if progress.is_complete and not progress.completed_at:
        progress.completed_at = timezone.now()
    progress.save()

    personalised_exercises = []
    try:
        from .services.lesson_quiz_adapter import process_course_quiz_submission
        summary = process_course_quiz_submission(request.user, lesson, results)
        personalised_exercises = summary.get("personalised_exercises", [])
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "course quiz adapter failed", exc_info=True
        )

    return render(request, "courses/lesson_quiz_result.html", {
        "course": course,
        "lesson": lesson,
        "quiz": quiz,
        "progress": progress,
        "score": score,
        "passed": progress.quiz_passed,
        "results": results,
        "personalised_exercises": personalised_exercises,
    })
