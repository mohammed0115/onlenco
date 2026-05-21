from __future__ import annotations

from django.urls import reverse

from notifications import constants as C
from notifications.models import NotificationEvent


def create_teacher_notification(*, teacher, event_type: str, actor=None, payload=None, priority=None):
    return NotificationEvent.objects.create(
        event_type=event_type,
        user=teacher,
        actor=actor,
        payload=payload or {},
        priority=priority or C.PRIORITY_NORMAL,
        status=C.STATUS_PROCESSED,
    )


# Lucide icon per teacher event type — used by the notifications page.
_TEACHER_EVENT_ICONS = {
    C.TEACHER_COURSE_APPROVED:         "check-circle",
    C.TEACHER_COURSE_REJECTED:         "alert-triangle",
    C.TEACHER_ASSIGNMENT_SUBMITTED:    "clipboard-list",
    C.TEACHER_STUDENT_LOW_PERFORMANCE: "user-round-x",
    C.TEACHER_CONTENT_NEEDS_REVISION:  "file-pen",
    C.TEACHER_DAILY_DIGEST:            "bell-ring",
}


def _teacher_event_url(event) -> str:
    """Best-effort deep link for a teacher notification, built from the
    event payload. Returns "" when no safe link can be made."""
    payload = event.payload or {}
    et = event.event_type
    try:
        if et in (C.TEACHER_COURSE_APPROVED, C.TEACHER_COURSE_REJECTED):
            if payload.get("course_id"):
                return reverse("teacher_portal:course_detail", args=[payload["course_id"]])
        elif et == C.TEACHER_ASSIGNMENT_SUBMITTED:
            if payload.get("assignment_id"):
                return reverse("teacher_portal:assignment_detail", args=[payload["assignment_id"]])
        elif et == C.TEACHER_STUDENT_LOW_PERFORMANCE:
            if payload.get("student_id"):
                return reverse("teacher_portal:student_detail", args=[payload["student_id"]])
            return reverse("teacher_portal:students")
        elif et == C.TEACHER_CONTENT_NEEDS_REVISION:
            return reverse("teacher_portal:all_lessons")
        elif et == C.TEACHER_DAILY_DIGEST:
            return reverse("teacher_portal:dashboard")
    except Exception:
        return ""
    return ""


def _digest_detail(payload) -> tuple[str, str]:
    """Build the (English, Arabic) summary line for a daily digest."""
    subs = int(payload.get("submissions_pending") or 0)
    fix = int(payload.get("content_to_fix") or 0)
    en, ar = [], []
    if subs:
        en.append(f"{subs} submissions to review")
        ar.append(f"{subs} تسليم بانتظار المراجعة")
    if fix:
        en.append(f"{fix} item(s) to revise")
        ar.append(f"{fix} عنصر يحتاج تعديلًا")
    return " · ".join(en), " · ".join(ar)


def describe_teacher_event(event) -> dict:
    """Turn a raw ``NotificationEvent`` into display-ready fields for the
    teacher notifications page: a human-readable bilingual title, an
    icon, a bilingual detail line, and a deep link — instead of dumping
    the raw event_type and JSON payload at the teacher.
    """
    payload = event.payload or {}
    if event.event_type == C.TEACHER_DAILY_DIGEST:
        detail_en, detail_ar = _digest_detail(payload)
    else:
        plain = (
            payload.get("course_title")
            or payload.get("lesson_title")
            or payload.get("notes")
            or ""
        )
        detail_en = detail_ar = plain
    return {
        "icon": _TEACHER_EVENT_ICONS.get(event.event_type, "bell"),
        "title_en": C.DEFAULT_SUBJECTS.get(
            event.event_type, event.event_type.replace("_", " ").capitalize(),
        ),
        "title_ar": C.SUBJECTS_AR.get(event.event_type, ""),
        "detail_en": detail_en,
        "detail_ar": detail_ar,
        "url": _teacher_event_url(event),
        "created_at": event.created_at,
    }


def send_daily_digests() -> dict:
    """Build and deliver a per-teacher daily digest of pending work.

    A teacher with nothing pending is skipped — no empty digests. Each
    digest is an in-app ``TEACHER_DAILY_DIGEST`` notification surfaced on
    the teacher's notifications page. Safe to call from a daily cron.
    """
    from django.contrib.auth import get_user_model
    from courses.models import Course, Lesson
    from teacher_portal.models import StudentAssignmentSubmission, TeacherAssignment

    User = get_user_model()
    teacher_ids = list(
        Course.objects.filter(teacher__isnull=False)
        .values_list("teacher_id", flat=True).distinct()
    )
    sent = 0
    for teacher in User.objects.filter(id__in=teacher_ids, is_active=True):
        courses = Course.objects.filter(teacher=teacher)
        assignments = TeacherAssignment.objects.filter(teacher=teacher)
        submissions_pending = StudentAssignmentSubmission.objects.filter(
            assignment__in=assignments, status="submitted",
        ).count()
        content_to_fix = (
            courses.filter(status="rejected").count()
            + Lesson.objects.filter(course__in=courses, status="rejected").count()
        )
        if submissions_pending == 0 and content_to_fix == 0:
            continue
        create_teacher_notification(
            teacher=teacher,
            event_type=C.TEACHER_DAILY_DIGEST,
            payload={
                "submissions_pending": submissions_pending,
                "content_to_fix": content_to_fix,
            },
        )
        sent += 1
    return {"teachers": len(teacher_ids), "digests_sent": sent}
