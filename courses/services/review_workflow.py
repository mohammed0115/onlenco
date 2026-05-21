"""Review workflow — submit / approve / reject — for Course + Lesson.

Both content types share the same state machine, so the helpers here
work on either via duck-typing on the `status` and the FK fields.
"""
from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .admin_log import log_admin_action
from ..models import ContentReviewLog


def submit_for_review(*, content_object, submitted_by) -> ContentReviewLog:
    """Flip `content_object.status` to `pending_review` and write a
    pending `ContentReviewLog` row."""
    content_object.status = "pending_review"
    content_object.save(update_fields=["status", "updated_at"]
                        if hasattr(content_object, "updated_at") else ["status"])
    log = ContentReviewLog.objects.create(
        content_type=ContentType.objects.get_for_model(content_object),
        object_id=content_object.id,
        submitted_by=submitted_by,
        status="pending",
    )
    log_admin_action(
        admin_user=submitted_by,
        action_type=f"{content_object._meta.model_name}.submit_for_review",
        description=f"Submitted '{content_object}' for review",
        metadata={"object_id": content_object.id},
    )
    return log


def approve(*, content_object, reviewed_by, notes: str = "") -> ContentReviewLog:
    """Flip status → `published` (Course/Lesson) and write the log row."""
    content_object.status = "published"
    content_object.reviewed_by = reviewed_by
    content_object.reviewed_at = timezone.now()
    if hasattr(content_object, "review_notes"):
        content_object.review_notes = notes
    fields = ["status", "reviewed_by", "reviewed_at"]
    if hasattr(content_object, "review_notes"):
        fields.append("review_notes")
    if hasattr(content_object, "updated_at"):
        fields.append("updated_at")
    content_object.save(update_fields=fields)
    log = ContentReviewLog.objects.create(
        content_type=ContentType.objects.get_for_model(content_object),
        object_id=content_object.id,
        reviewed_by=reviewed_by,
        status="approved",
        notes=notes,
    )
    log_admin_action(
        admin_user=reviewed_by,
        action_type=f"{content_object._meta.model_name}.approve",
        description=f"Approved '{content_object}'",
        metadata={"object_id": content_object.id},
    )
    return log


def reject(*, content_object, reviewed_by, notes: str = "") -> ContentReviewLog:
    """Reject content and store notes.

    Courses and the new teacher-portal lessons both have a first-class
    `rejected` state so instructors can revise from explicit feedback.
    """
    content_object.status = "rejected"
    content_object.reviewed_by = reviewed_by
    content_object.reviewed_at = timezone.now()
    if hasattr(content_object, "review_notes"):
        content_object.review_notes = notes
    fields = ["status", "reviewed_by", "reviewed_at"]
    if hasattr(content_object, "review_notes"):
        fields.append("review_notes")
    if hasattr(content_object, "updated_at"):
        fields.append("updated_at")
    content_object.save(update_fields=fields)
    log = ContentReviewLog.objects.create(
        content_type=ContentType.objects.get_for_model(content_object),
        object_id=content_object.id,
        reviewed_by=reviewed_by,
        status="rejected",
        notes=notes,
    )
    log_admin_action(
        admin_user=reviewed_by,
        action_type=f"{content_object._meta.model_name}.reject",
        description=f"Rejected '{content_object}'",
        metadata={"object_id": content_object.id, "notes": notes[:200]},
    )
    _notify_author_on_reject(content_object, notes)
    return log


def _notify_author_on_reject(content_object, notes: str) -> None:
    """Tell a teacher their lesson needs revision.

    Course rejections are notified separately by the course-review
    service, so this fires only for lessons (whose rejection had no
    teacher-facing notification at all). Best-effort — a notification
    failure must never block the rejection itself.
    """
    if content_object._meta.model_name != "lesson":
        return
    teacher = getattr(content_object, "created_by", None)
    if teacher is None:
        return
    try:
        from notifications import constants as C
        from teacher_portal.services.notification_service import create_teacher_notification
        create_teacher_notification(
            teacher=teacher,
            event_type=C.TEACHER_CONTENT_NEEDS_REVISION,
            payload={
                "lesson_id": content_object.id,
                "lesson_title": getattr(content_object, "title", ""),
                "notes": notes,
            },
        )
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "review_workflow: teacher revision notice failed", exc_info=True,
        )
