"""Admin-only, audited override for the strict placement gate.

Lets an admin explicitly finalise a student's placement (assign a level +
course) when the normal speaking gate can't be satisfied — e.g. a hardware
/ connectivity problem on the student's side. This is NEVER automatic for
normal students; it requires an admin actor + a reason, and the action is
recorded for audit.
"""
from __future__ import annotations

from django.utils import timezone

from accounts.models import CEFR_CHOICES
from placement.models import (
    PlacementAttempt, PlacementResult, PlacementSpeakingAttempt,
)

VALID_LEVELS = {code for code, _ in CEFR_CHOICES}


class OverrideError(Exception):
    """Raised when the admin override is rejected (missing reason/level)."""


def admin_finalise_placement(*, student, actor, reason: str, level: str):
    """Force-finalise ``student``'s placement at ``level`` with an audit trail.

    Returns ``(attempt, result)``. Raises ``OverrideError`` on bad input.
    """
    reason = (reason or "").strip()
    if not reason:
        raise OverrideError("A reason is required for an admin override.")
    level = (level or "").strip().upper()
    if level not in VALID_LEVELS:
        raise OverrideError(f"Invalid level '{level}'.")

    attempt = (
        PlacementAttempt.objects.filter(user=student).exclude(status="completed")
        .order_by("-started_at").first()
        or PlacementAttempt.objects.filter(user=student).order_by("-started_at").first()
    )
    if attempt is None:
        attempt = PlacementAttempt.objects.create(user=student, status="started")

    # Score the written part deterministically if possible (lazy import to
    # avoid a views<->services import cycle).
    from placement.views import grade_written_section
    written = grade_written_section(attempt)
    if written is None:
        written = attempt.written_score or 0
    speaking = attempt.speaking_score or 0

    attempt.written_score = written
    attempt.overall_score = int(round((written + speaking) / 2))
    attempt.recommended_cefr_level = level
    attempt.status = "completed"
    attempt.completed_at = timezone.now()
    result = PlacementResult.objects.create(
        user=student, level=level,
        written_score=written, speaking_score=speaking,
        overall_score=attempt.overall_score,
        feedback="Finalised by admin override.",
        transcript={
            "source": "admin_override",
            "actor_id": getattr(actor, "id", None),
            "reason": reason[:2000],
            "at": timezone.now().isoformat(),
        },
    )
    attempt.result = result
    attempt.save(update_fields=[
        "written_score", "overall_score", "recommended_cefr_level",
        "status", "completed_at", "result",
    ])

    # Audit on the speaking attempt (mark completed + record who/why).
    conv = attempt.voice_conversation
    row = (
        PlacementSpeakingAttempt.objects
        .filter(student=student).order_by("-started_at").first()
    )
    if row is None:
        row = PlacementSpeakingAttempt.objects.create(
            student=student, conversation=conv, placement_attempt=attempt)
    row.status = PlacementSpeakingAttempt.STATUS_COMPLETED
    row.is_used_attempt = True
    md = dict(row.metadata or {})
    md.update({
        "admin_override": True,
        "override_actor_id": getattr(actor, "id", None),
        "override_reason": reason[:2000],
        "override_at": timezone.now().isoformat(),
    })
    row.metadata = md
    row.save()

    # Profile + course assignment.
    try:
        profile = student.profile
        profile.cefr_level = level
        if not profile.initial_cefr_level:
            profile.initial_cefr_level = level
        profile.placement_completed = True
        profile.save(update_fields=["cefr_level", "initial_cefr_level", "placement_completed"])
        from accounts.onboarding import complete_placement_onboarding
        complete_placement_onboarding(profile, level=level)
    except Exception:
        pass

    return attempt, result
