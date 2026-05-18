"""Club lifecycle helpers — attendance marking + feedback submission."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import ClubEvent, ClubFeedback, ClubRSVP


@transaction.atomic
def mark_attendance(*, rsvp: ClubRSVP, marked_by, attended: bool = True) -> ClubRSVP:
    """Flip a RSVP's ``attended`` flag and stamp the marker."""
    rsvp.attended = attended
    rsvp.attendance_marked_at = timezone.now() if attended else None
    rsvp.attendance_marked_by = marked_by if attended else None
    rsvp.save(update_fields=["attended", "attendance_marked_at", "attendance_marked_by", "updated_at"])
    return rsvp


@transaction.atomic
def submit_feedback(
    *,
    event: ClubEvent,
    student,
    author,
    rating: int,
    feedback_en: str = "",
    feedback_ar: str = "",
    xp_awarded: int = 0,
    is_visible_to_student: bool = True,
) -> ClubFeedback:
    """Create or update a teacher's feedback for a student in a club session."""
    fb, _ = ClubFeedback.objects.update_or_create(
        event=event, student=student,
        defaults={
            "author": author,
            "rating": max(1, min(5, int(rating or 3))),
            "feedback_en": feedback_en or "",
            "feedback_ar": feedback_ar or "",
            "xp_awarded": max(0, int(xp_awarded or 0)),
            "is_visible_to_student": bool(is_visible_to_student),
        },
    )
    if xp_awarded:
        try:
            from motivation.services.xp_service import grant_xp_for
            grant_xp_for(student, source="club_feedback", amount=xp_awarded)
        except Exception:
            pass
    return fb


def event_attendance_summary(event: ClubEvent) -> dict:
    rsvps = event.rsvps.select_related("user")
    going = rsvps.filter(status="going").count()
    attended = rsvps.filter(attended=True).count()
    return {
        "registered": rsvps.count(),
        "going": going,
        "attended": attended,
        "no_show": max(0, going - attended),
    }
