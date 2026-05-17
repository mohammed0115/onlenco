from __future__ import annotations

from courses.services import review_workflow
from platform_admin.services.audit_log_service import log_action

from .course_service import save_lesson_worksheet


def create_lesson(request, form, course):
    lesson = form.save(commit=False)
    lesson.course = course
    lesson.created_by = request.user
    lesson.status = "draft"
    lesson.save()
    save_lesson_worksheet(lesson=lesson, form=form)
    log_action(
        request,
        action_type="teacher.lesson.create",
        object_type="Lesson",
        object_id=lesson.pk,
        description=f"Teacher created lesson '{lesson.title}'",
        metadata={"course_id": course.pk},
    )
    return lesson


def update_lesson(request, form):
    lesson = form.save()
    save_lesson_worksheet(lesson=lesson, form=form)
    log_action(
        request,
        action_type="teacher.lesson.update",
        object_type="Lesson",
        object_id=lesson.pk,
        description=f"Teacher updated lesson '{lesson.title}'",
        metadata={"course_id": lesson.course_id},
    )
    return lesson


def submit_lesson_for_review(request, lesson):
    log = review_workflow.submit_for_review(content_object=lesson, submitted_by=request.user)
    log_action(
        request,
        action_type="teacher.lesson.submit_review",
        object_type="Lesson",
        object_id=lesson.pk,
        description=f"Teacher submitted lesson '{lesson.title}' for review",
        metadata={"course_id": lesson.course_id},
    )
    return log

