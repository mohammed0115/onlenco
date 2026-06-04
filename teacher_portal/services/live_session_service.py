"""Live-session orchestration: notifications on schedule + 30-min reminders."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from notifications import constants as C

logger = logging.getLogger(__name__)

# How long before a session the reminder goes out.
REMINDER_WINDOW_MINUTES = 30
# Grace floor so a late/skipped scheduler tick still catches a just-due
# session instead of losing the reminder forever once it crosses "now".
REMINDER_GRACE_MINUTES = 10


def _course_title(course) -> str:
    return getattr(course, "title_en", "") or getattr(course, "title_ar", "") or getattr(course, "title", "") or ""


def _active_students(course):
    """Active enrolled students of the course (the teacher's audience)."""
    return [e.user for e in course.enrollments.filter(status="active").select_related("user")]


def _local_dt(dt) -> str:
    return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M")


def notify_students_scheduled(session) -> int:
    """Fan out LIVE_SESSION_SCHEDULED to every active student of the course.

    Best-effort: a notification failure never blocks scheduling. Returns the
    number of students notified.
    """
    from notifications.services import NotificationService

    teacher = session.teacher
    teacher_name = teacher.get_full_name() or teacher.get_username()
    notifier = NotificationService()
    count = 0
    for student in _active_students(session.course):
        try:
            notifier.trigger(
                C.LIVE_SESSION_SCHEDULED,
                user=student,
                actor=teacher,
                payload={
                    "title": session.title,
                    "course_title": _course_title(session.course),
                    "teacher_name": teacher_name,
                    "scheduled_at": _local_dt(session.scheduled_at),
                    "duration_minutes": session.duration_minutes,
                    "cta_url": session.meet_link or "/dashboard/",
                    "cta_label": "Join",
                    "dedup_key": f"live_sched:{session.pk}:{student.pk}",
                },
            )
            count += 1
        except Exception:
            logger.exception("live session schedule notify failed for student=%s", student.pk)
    return count


def due_reminders(now=None):
    """Scheduled sessions starting within the next REMINDER_WINDOW that
    haven't had a reminder yet."""
    from teacher_portal.models import LiveSession

    now = now or timezone.now()
    horizon = now + timedelta(minutes=REMINDER_WINDOW_MINUTES)
    floor = now - timedelta(minutes=REMINDER_GRACE_MINUTES)
    return (
        LiveSession.objects
        .filter(status="scheduled", reminder_sent_at__isnull=True, scheduled_at__gte=floor, scheduled_at__lte=horizon)
        .select_related("course", "teacher")
    )


def send_reminders(now=None) -> dict:
    """Send the 30-minute reminder for every due session. Idempotent via
    ``reminder_sent_at``. Returns counts."""
    from notifications.services import NotificationService

    now = now or timezone.now()
    notifier = NotificationService()
    sessions = 0
    students = 0
    for session in due_reminders(now):
        for student in _active_students(session.course):
            try:
                notifier.trigger(
                    C.LIVE_SESSION_REMINDER,
                    user=student,
                    actor=session.teacher,
                    payload={
                        "title": session.title,
                        "course_title": _course_title(session.course),
                        "scheduled_at": _local_dt(session.scheduled_at),
                        "cta_url": session.meet_link or "/dashboard/",
                        "cta_label": "Join now",
                        "dedup_key": f"live_remind:{session.pk}:{student.pk}",
                    },
                )
                students += 1
            except Exception:
                logger.exception("live session reminder failed for student=%s", student.pk)
        session.reminder_sent_at = now
        session.save(update_fields=["reminder_sent_at"])
        sessions += 1
    return {"sessions": sessions, "students": students}
