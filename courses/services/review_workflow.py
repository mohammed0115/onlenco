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
    """Flip status back to `draft` and store the rejection notes."""
    content_object.status = "draft"
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
    return log
