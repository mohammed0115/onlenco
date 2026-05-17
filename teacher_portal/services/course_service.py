from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify

from courses.models import ContentReviewLog, Course, LessonResource
from courses.services import review_workflow
from notifications import constants as C
from platform_admin.services.audit_log_service import log_action

from .notification_service import create_teacher_notification


def unique_course_slug(title: str) -> str:
    base = slugify(title, allow_unicode=True) or "course"
    slug = base[:200]
    counter = 2
    while Course.objects.filter(slug=slug).exists():
        suffix = f"-{counter}"
        slug = f"{base[:220-len(suffix)]}{suffix}"
        counter += 1
    return slug


def create_course(request, form):
    course = form.save(commit=False)
    course.teacher = request.user
    course.created_by = request.user
    course.status = "draft"
    course.slug = unique_course_slug(course.title)
    course.save()
    log_action(
        request,
        action_type="teacher.course.create",
        object_type="Course",
        object_id=course.pk,
        description=f"Teacher created course '{course.title}'",
    )
    return course


def update_course(request, form):
    course = form.save()
    log_action(
        request,
        action_type="teacher.course.update",
        object_type="Course",
        object_id=course.pk,
        description=f"Teacher updated course '{course.title}'",
    )
    return course


def submit_course_for_review(request, course):
    log = review_workflow.submit_for_review(content_object=course, submitted_by=request.user)
    log_action(
        request,
        action_type="teacher.course.submit_review",
        object_type="Course",
        object_id=course.pk,
        description=f"Teacher submitted course '{course.title}' for review",
    )
    return log


def ensure_review_log(content_object, submitted_by):
    return ContentReviewLog.objects.create(
        content_type=ContentType.objects.get_for_model(content_object),
        object_id=content_object.id,
        submitted_by=submitted_by,
        status="pending",
    )


def save_lesson_worksheet(*, lesson, form):
    file = form.cleaned_data.get("worksheet_file")
    if not file:
        return None
    return LessonResource.objects.create(
        lesson=lesson,
        resource_type="worksheet",
        title=form.cleaned_data.get("worksheet_title") or "Worksheet",
        file=file,
    )


def notify_course_review_result(course, reviewer, approved: bool, notes: str = ""):
    if not course.teacher_id:
        return None
    event_type = C.TEACHER_COURSE_APPROVED if approved else C.TEACHER_COURSE_REJECTED
    return create_teacher_notification(
        teacher=course.teacher,
        actor=reviewer,
        event_type=event_type,
        payload={"course_id": course.pk, "course_title": course.title, "notes": notes},
    )
