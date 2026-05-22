from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone

from courses.models import Course, ContentReviewLog, Lesson, LessonResource
from platform_admin.permissions import courses_for_user
from platform_admin.services.audit_log_service import log_action


def course_queryset_for(user, params=None):
    qs = courses_for_user(
        user,
        Course.objects.select_related("level", "teacher", "created_by").annotate(
            lessons_count=Count("lessons", distinct=True),
            students_count=Count("enrollments", distinct=True),
        ),
    )
    params = params or {}
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q) | Q(teacher__email__icontains=q))
    level = (params.get("level") or "").strip()
    if level:
        qs = qs.filter(level__code=level)
    status = (params.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    language = (params.get("language") or "").strip()
    if language:
        qs = qs.filter(language=language)
    teacher_id = (params.get("teacher") or "").strip()
    if teacher_id.isdigit():
        qs = qs.filter(teacher_id=int(teacher_id))
    return _apply_course_sort(qs, params)


# Sortable columns on the admin course list. Maps the public sort key
# (used in the ?sort= URL param) to the ORM field — a whitelist, so an
# arbitrary ?sort= value can never reach order_by().
COURSE_SORT_FIELDS = {
    "title": "title",
    "level": "level__code",
    "teacher": "teacher__email",
    "status": "status",
    "lessons": "lessons_count",
    "students": "students_count",
    "updated": "updated_at",
}


def _apply_course_sort(qs, params):
    """Order ``qs`` by the whitelisted ``?sort=`` key (a leading '-' = desc).

    Falls back to most-recently-updated when the key is missing or not
    recognised. ``-created_at`` is always appended as a stable tiebreaker.
    """
    sort = (params.get("sort") or "").strip()
    key = sort[1:] if sort.startswith("-") else sort
    field = COURSE_SORT_FIELDS.get(key)
    if not field:
        return qs.order_by("-updated_at", "-created_at")
    prefix = "-" if sort.startswith("-") else ""
    return qs.order_by(f"{prefix}{field}", "-created_at")


def course_sort_headers(params):
    """Per-column sort metadata for the course-list table header.

    Returns ``{key: {"param", "active", "desc"}}`` where ``param`` is the
    value to feed the next ``?sort=`` (clicking an ascending column flips
    it to descending), ``active`` marks the current sort column, and
    ``desc`` says the current sort is descending.
    """
    current = (params.get("sort") or "").strip()
    headers = {}
    for key in COURSE_SORT_FIELDS:
        headers[key] = {
            "param": f"-{key}" if current == key else key,
            "active": current in (key, f"-{key}"),
            "desc": current == f"-{key}",
        }
    return headers


def pending_review_queryset_for(user):
    return course_queryset_for(user, {"status": "pending_review"})


def course_detail_context(course) -> dict:
    return {
        "course": course,
        "units": course.units.all(),
        "lessons": course.lessons.select_related("unit", "created_by").prefetch_related("resources").all(),
        "quizzes": [],
        "resources_count": LessonResource.objects.filter(lesson__course=course).count(),
        "enrollments": course.enrollments.select_related("user")[:100],
        "review_logs": ContentReviewLog.objects.filter(object_id=course.pk, content_type__model="course")[:20],
    }


def approve_course(request, course, notes: str = ""):
    old_status = course.status
    course.status = "published"
    course.reviewed_by = request.user
    course.reviewed_at = timezone.now()
    course.review_notes = notes
    course.is_active = True
    course.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes", "is_active", "updated_at"])
    log_action(
        request,
        action_type="course.approve",
        object_type="Course",
        object_id=course.pk,
        description=f"Approved course '{course.title}'",
        metadata={"old_status": old_status, "new_status": course.status, "notes": notes[:500]},
    )
    try:
        from teacher_portal.services.course_service import notify_course_review_result
        notify_course_review_result(course, request.user, approved=True, notes=notes)
    except Exception:
        pass


def reject_course(request, course, notes: str):
    old_status = course.status
    course.status = "rejected"
    course.reviewed_by = request.user
    course.reviewed_at = timezone.now()
    course.review_notes = notes
    course.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes", "updated_at"])
    log_action(
        request,
        action_type="course.reject",
        object_type="Course",
        object_id=course.pk,
        description=f"Rejected course '{course.title}'",
        metadata={"old_status": old_status, "new_status": course.status, "notes": notes[:500]},
    )
    try:
        from teacher_portal.services.course_service import notify_course_review_result
        notify_course_review_result(course, request.user, approved=False, notes=notes)
    except Exception:
        pass


def publish_course(request, course):
    old_status = course.status
    course.status = "published"
    course.is_active = True
    course.save(update_fields=["status", "is_active", "updated_at"])
    log_action(
        request,
        action_type="course.publish",
        object_type="Course",
        object_id=course.pk,
        description=f"Published course '{course.title}'",
        metadata={"old_status": old_status, "new_status": course.status},
    )


def archive_course(request, course):
    old_status = course.status
    course.status = "archived"
    course.is_active = False
    course.save(update_fields=["status", "is_active", "updated_at"])
    log_action(
        request,
        action_type="course.archive",
        object_type="Course",
        object_id=course.pk,
        description=f"Archived course '{course.title}'",
        metadata={"old_status": old_status, "new_status": course.status},
    )


def save_lesson_with_worksheet(request, form, *, course, lesson: Lesson | None = None) -> Lesson:
    created = lesson is None
    lesson = form.save(commit=False)
    lesson.course = course
    if created and lesson.created_by_id is None:
        lesson.created_by = request.user
    lesson.save()

    worksheet_file = form.cleaned_data.get("worksheet_file")
    worksheet_title = form.cleaned_data.get("worksheet_title") or "Worksheet"
    if worksheet_file:
        LessonResource.objects.create(
            lesson=lesson,
            resource_type="worksheet",
            title=worksheet_title,
            file=worksheet_file,
            order=lesson.resources.count() + 1,
        )

    log_action(
        request,
        action_type="lesson.create" if created else "lesson.update",
        object_type="Lesson",
        object_id=lesson.pk,
        description=f"{'Created' if created else 'Updated'} video lesson '{lesson.title}'",
        metadata={
            "course_id": course.pk,
            "has_video_file": bool(lesson.video_file),
            "has_video_url": bool(lesson.video_url),
            "worksheet_uploaded": bool(worksheet_file),
        },
    )
    return lesson
