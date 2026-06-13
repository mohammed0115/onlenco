"""Phase 11 — Lesson review workflow + audit trail (Phase 11 specific).

A separate module from the older `review_workflow.py` (which handles
the legacy submit/approve flow for Course+Lesson generically). This
one is opinionated for the Phase-10 generated lesson lifecycle.

State machine:

  pending_review ──→ in_review ──→ changes_requested
       │              │                  │
       │              ↓                  │ (loops back to in_review)
       │            approved ←──────────┘
       │              │
       │              ↓
       │            published
       │              │
       │              ↓
       └─→ rejected  archived  (terminal)

Every transition writes a `LessonReviewEvent`. `approve()` runs the
quality checker first and refuses if any "error" flag is present
(admins can pass `override=True`). `publish()` requires `approved`.
"""
from __future__ import annotations

from typing import Optional

from django.db import transaction
from django.utils import timezone

from courses.models import Lesson, LessonReviewEvent
from courses.services import content_quality_checker


class WorkflowError(Exception):
    """User-correctable. Maps to 4xx upstream."""


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------

@transaction.atomic
def start_review(*, actor, lesson: Lesson, note: str = "") -> Lesson:
    if lesson.status not in {"pending_review", "changes_requested"}:
        raise WorkflowError(
            f"Cannot start review on a lesson with status '{lesson.status}'."
        )
    return _transition(
        lesson=lesson, actor=actor, to_status="in_review",
        action="start_review", note=note,
    )


@transaction.atomic
def request_changes(*, actor, lesson: Lesson, note: str) -> Lesson:
    if not (note or "").strip():
        raise WorkflowError("A note is required when requesting changes.")
    if lesson.status not in {"in_review", "pending_review"}:
        raise WorkflowError(
            f"Cannot request changes from status '{lesson.status}'."
        )
    return _transition(
        lesson=lesson, actor=actor, to_status="changes_requested",
        action="request_changes", note=note,
    )


@transaction.atomic
def approve(*, actor, lesson: Lesson, note: str = "", override: bool = False) -> Lesson:
    if lesson.status not in {"in_review", "changes_requested", "pending_review"}:
        raise WorkflowError(
            f"Cannot approve a lesson with status '{lesson.status}'."
        )
    result = content_quality_checker.check_lesson_quality(lesson)
    has_errors = any(f["severity"] == "error" for f in result["flags"])
    if has_errors and not override:
        raise WorkflowError(
            "Cannot approve — quality checker reported errors. "
            "Fix the errors or pass override=True (admin only)."
        )

    lesson.approved_by = actor
    lesson.approved_at = timezone.now()
    lesson.quality_score = int(result["score"])
    lesson.quality_flags = [
        {"severity": f["severity"], "code": f["code"], "message": f["message"]}
        for f in result["flags"]
    ]
    lesson.save(update_fields=[
        "approved_by", "approved_at", "quality_score", "quality_flags", "updated_at",
    ])
    return _transition(
        lesson=lesson, actor=actor, to_status="approved",
        action="approve", note=note,
        metadata={"quality_score": result["score"], "override": bool(override)},
    )


@transaction.atomic
def publish(*, actor, lesson: Lesson, note: str = "") -> Lesson:
    if lesson.status != "approved":
        raise WorkflowError(
            f"Cannot publish a lesson with status '{lesson.status}'. "
            "It must be approved first."
        )
    lesson.published_at = timezone.now()
    lesson.save(update_fields=["published_at", "updated_at"])
    return _transition(
        lesson=lesson, actor=actor, to_status="published",
        action="publish", note=note,
    )


@transaction.atomic
def unpublish(*, actor, lesson: Lesson, note: str = "") -> Lesson:
    if lesson.status != "published":
        raise WorkflowError(
            f"Cannot unpublish a lesson with status '{lesson.status}'."
        )
    return _transition(
        lesson=lesson, actor=actor, to_status="approved",
        action="unpublish", note=note,
    )


@transaction.atomic
def reject(*, actor, lesson: Lesson, note: str) -> Lesson:
    if not (note or "").strip():
        raise WorkflowError("A note is required when rejecting.")
    return _transition(
        lesson=lesson, actor=actor, to_status="rejected",
        action="reject", note=note,
    )


@transaction.atomic
def add_note(*, actor, lesson: Lesson, note: str) -> LessonReviewEvent:
    if not (note or "").strip():
        raise WorkflowError("Note text cannot be empty.")
    return LessonReviewEvent.objects.create(
        lesson=lesson, actor=actor,
        from_status=lesson.status, to_status="",
        action="note_added", note=note,
    )


@transaction.atomic
def set_access_override(*, actor, lesson: Lesson, access: str, note: str = "") -> Lesson:
    """Admin lock/unlock for a single lesson.

    ``access`` is one of ``Lesson.ACCESS_INHERIT`` / ``ACCESS_FREE`` /
    ``ACCESS_LOCKED``. Writes a ``LessonReviewEvent`` so the change shows
    up in the lesson's audit trail. Does NOT touch the publish status.
    """
    valid = {Lesson.ACCESS_INHERIT, Lesson.ACCESS_FREE, Lesson.ACCESS_LOCKED}
    if access not in valid:
        raise WorkflowError(f"Unknown access value '{access}'.")
    prev = lesson.access_override
    if prev != access:
        lesson.access_override = access
        lesson.save(update_fields=["access_override", "updated_at"])
    LessonReviewEvent.objects.create(
        lesson=lesson, actor=actor,
        from_status=lesson.status, to_status="",
        action="set_access", note=note or "",
        metadata={"from_access": prev, "to_access": access},
    )
    return lesson


def record_quality_check(
    *, actor, lesson: Lesson, score: int, flags_count: int,
) -> LessonReviewEvent:
    return LessonReviewEvent.objects.create(
        lesson=lesson, actor=actor,
        from_status=lesson.status, to_status="",
        action="quality_check", note="",
        quality_score=int(score),
        metadata={"flags_count": int(flags_count)},
    )


# ---------------------------------------------------------------------------
# Internal.
# ---------------------------------------------------------------------------

def _transition(
    *, lesson: Lesson, actor, to_status: str, action: str,
    note: str = "", metadata: Optional[dict] = None,
) -> Lesson:
    prev = lesson.status
    if to_status != prev:
        lesson.status = to_status
        if action in {"start_review", "approve", "request_changes", "reject"}:
            lesson.reviewed_by = actor
            lesson.reviewed_at = timezone.now()
        update_fields = ["status", "reviewed_by", "reviewed_at", "updated_at"]
        lesson.save(update_fields=update_fields)
    LessonReviewEvent.objects.create(
        lesson=lesson, actor=actor,
        from_status=prev, to_status=to_status,
        action=action, note=note or "",
        metadata=metadata or {},
    )
    return lesson
