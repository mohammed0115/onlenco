"""Phase 11 — Teacher/Admin Content Review Dashboard.

Routes (registered in `teacher_portal.urls`):

  /teacher/content-review/                                   list
  /teacher/content-review/lessons/<int:lesson_id>/           detail
  /teacher/content-review/lessons/<int:lesson_id>/start-review/   (POST)
  /teacher/content-review/lessons/<int:lesson_id>/approve/        (POST)
  /teacher/content-review/lessons/<int:lesson_id>/request-changes/(POST)
  /teacher/content-review/lessons/<int:lesson_id>/publish/        (POST)
  /teacher/content-review/lessons/<int:lesson_id>/unpublish/      (POST)
  /teacher/content-review/lessons/<int:lesson_id>/note/           (POST)

All gated by `teacher_required` (admins are included via that decorator
in this project — see `RoleService.user_has_role`).
"""
from __future__ import annotations

from django.contrib import messages
from django.db.models import Count
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from courses.models import (
    Lesson, LessonAudioScript, LessonChecklist, LessonImagePrompt,
    LessonReviewEvent, LessonQuestion,
)
from courses.services import (
    content_quality_checker, lesson_review_workflow as workflow,
)
from .permissions import teacher_required


# Statuses the dashboard surfaces by default.
REVIEWABLE_STATUSES = (
    "pending_review", "in_review", "changes_requested",
    "approved", "published", "rejected",
)


@teacher_required
def content_review_list(request):
    """List view — filter / search across lessons that need a teacher's eye."""
    qs = (
        Lesson.objects.select_related("course")
        .filter(status__in=REVIEWABLE_STATUSES)
        .annotate(question_count=Count("quiz__questions"))
        .order_by("course__slug", "order")
    )

    # Filters
    status = request.GET.get("status", "").strip()
    course_slug = request.GET.get("course", "").strip()
    has_warnings = request.GET.get("warnings", "").strip()
    fallback_skill = request.GET.get("fallback", "").strip()
    search = request.GET.get("q", "").strip()

    if status and status in dict([(s, s) for s in REVIEWABLE_STATUSES]):
        qs = qs.filter(status=status)
    if course_slug:
        qs = qs.filter(course__slug=course_slug)
    if search:
        qs = qs.filter(title__icontains=search)

    lessons = list(qs)

    # In-Python post-filtering for JSON-flag predicates.
    def _has_flag_code(lesson, code):
        for f in (lesson.quality_flags or []):
            if f.get("code") == code:
                return True
        return False

    if has_warnings == "1":
        lessons = [l for l in lessons if l.quality_flags]
    if fallback_skill == "1":
        lessons = [l for l in lessons if _has_flag_code(l, "fallback_skill")]

    return render(request, "teacher_portal/content_review/list.html", {
        "lessons": lessons,
        "status_filter": status,
        "search": search,
        "course_filter": course_slug,
        "warnings_filter": has_warnings,
        "fallback_filter": fallback_skill,
        "available_statuses": REVIEWABLE_STATUSES,
    })


@teacher_required
def content_review_detail(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related("course"),
        pk=lesson_id,
    )
    # Re-compute live quality (don't persist — `approve` does that).
    quality = content_quality_checker.check_lesson_quality(lesson)

    questions = list(lesson.quiz.questions.all().order_by("order")) if hasattr(lesson, "quiz") else []
    image_prompts = list(LessonImagePrompt.objects.filter(lesson=lesson))
    audio_scripts = list(LessonAudioScript.objects.filter(lesson=lesson))
    checklist = list(LessonChecklist.objects.filter(lesson=lesson, is_active=True).order_by("sort_order"))
    events = list(
        LessonReviewEvent.objects.filter(lesson=lesson)
        .select_related("actor").order_by("-created_at")[:50]
    )

    return render(request, "teacher_portal/content_review/detail.html", {
        "lesson": lesson,
        "quality": quality,
        "questions": questions,
        "image_prompts": image_prompts,
        "audio_scripts": audio_scripts,
        "checklist": checklist,
        "events": events,
    })


# ---------------------------------------------------------------------------
# Action handlers (POST only).
# ---------------------------------------------------------------------------

def _do_action(request, lesson_id, fn, *, default_redirect=True):
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    note = (request.POST.get("note") or "").strip()
    override = bool(request.POST.get("override"))
    try:
        if fn is workflow.approve:
            fn(actor=request.user, lesson=lesson, note=note, override=override)
        elif fn in {workflow.request_changes, workflow.reject, workflow.add_note}:
            fn(actor=request.user, lesson=lesson, note=note)
        else:
            fn(actor=request.user, lesson=lesson, note=note)
        messages.success(request, f"Action {fn.__name__} succeeded.")
    except workflow.WorkflowError as exc:
        messages.error(request, str(exc))
    if default_redirect:
        return redirect("teacher_portal:content_review_detail", lesson_id=lesson.pk)
    return JsonResponse({"ok": True})


@teacher_required
@require_POST
def action_start_review(request, lesson_id):
    return _do_action(request, lesson_id, workflow.start_review)


@teacher_required
@require_POST
def action_request_changes(request, lesson_id):
    return _do_action(request, lesson_id, workflow.request_changes)


@teacher_required
@require_POST
def action_approve(request, lesson_id):
    return _do_action(request, lesson_id, workflow.approve)


@teacher_required
@require_POST
def action_publish(request, lesson_id):
    return _do_action(request, lesson_id, workflow.publish)


@teacher_required
@require_POST
def action_unpublish(request, lesson_id):
    return _do_action(request, lesson_id, workflow.unpublish)


@teacher_required
@require_POST
def action_add_note(request, lesson_id):
    return _do_action(request, lesson_id, workflow.add_note)


@teacher_required
@require_POST
def action_set_access(request, lesson_id):
    """Lock / unlock a single lesson (per-lesson access override)."""
    lesson = get_object_or_404(Lesson, pk=lesson_id)
    access = (request.POST.get("access") or "").strip()
    note = (request.POST.get("note") or "").strip()
    try:
        workflow.set_access_override(
            actor=request.user, lesson=lesson, access=access, note=note,
        )
        label = {
            Lesson.ACCESS_INHERIT: "inherits the course rule",
            Lesson.ACCESS_FREE: "unlocked (free — always open)",
            Lesson.ACCESS_LOCKED: "locked (subscription required)",
        }.get(access, access)
        messages.success(request, f"Lesson access updated — now {label}.")
    except workflow.WorkflowError as exc:
        messages.error(request, str(exc))
    return redirect("teacher_portal:content_review_detail", lesson_id=lesson.pk)
