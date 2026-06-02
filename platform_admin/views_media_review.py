"""Prompt 15 — generated-media review queue (control panel).

Teacher/admin preview generated images/audio and approve/reject them. Only
approved media reaches students. All actions update the review fields.
"""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from courses.models import LessonAudioScript, LessonImagePrompt
from courses.services import media_generation_service as svc

from teacher_portal.permissions import teacher_required

GENERATED_STATUSES = {"generated", "needs_review", "approved", "rejected", "failed"}


@teacher_required
def media_review(request):
    status = request.GET.get("status", "needs_review")
    media_type = request.GET.get("media_type", "")
    img = LessonImagePrompt.objects.select_related("lesson").exclude(
        generation_status="pending_generation")
    aud = LessonAudioScript.objects.select_related("lesson").exclude(
        generation_status="pending_generation")
    if status:
        img = img.filter(generation_status=status)
        aud = aud.filter(generation_status=status)

    rows = []
    if media_type != "audio":
        for ip in img.order_by("lesson__order", "prompt_type")[:200]:
            rows.append({"id": ip.id, "media_type": "image", "purpose": ip.prompt_type,
                         "topic": ip.lesson.order, "title": ip.lesson.title,
                         "status": ip.generation_status,
                         "url": ip.generated_image.url if ip.generated_image else "",
                         "cost": ip.ai_usage_log.estimated_cost_usd if ip.ai_usage_log else None,
                         "error": ip.gen_error_message})
    if media_type != "image":
        for sc in aud.order_by("lesson__order", "script_type")[:200]:
            rows.append({"id": sc.id, "media_type": "audio", "purpose": sc.script_type,
                         "topic": sc.lesson.order, "title": sc.lesson.title,
                         "status": sc.generation_status,
                         "url": sc.generated_audio.url if sc.generated_audio else "",
                         "cost": sc.ai_usage_log.estimated_cost_usd if sc.ai_usage_log else None,
                         "error": sc.gen_error_message})
    rows.sort(key=lambda r: (r["topic"], r["media_type"], r["purpose"]))
    return render(request, "platform_admin/media/review.html", {
        "rows": rows, "status": status, "media_type": media_type,
        "statuses": sorted(GENERATED_STATUSES), "section": "media_review"})


def _get(media_type, pk):
    Model = LessonImagePrompt if media_type == "image" else LessonAudioScript
    return get_object_or_404(Model, pk=pk)


@require_POST
@teacher_required
def media_action(request, media_type, pk, action):
    obj = _get(media_type, pk)
    note = (request.POST.get("note") or "").strip()
    if action == "approve":
        svc.mark_media_approved(obj, request.user, note)
        messages.success(request, "Media approved — now visible to students.")
    elif action == "reject":
        svc.mark_media_rejected(obj, request.user, note)
        messages.success(request, "Media rejected — students keep the placeholder.")
    elif action == "note":
        obj.review_notes = note
        obj.save(update_fields=["review_notes", "updated_at"])
        messages.success(request, "Note saved.")
    else:
        messages.error(request, "Unknown action.")
    return redirect(request.META.get("HTTP_REFERER") or "platform_admin:media_review")
