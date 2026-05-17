from __future__ import annotations

from django.utils import timezone

from notifications import constants as C
from platform_admin.services.audit_log_service import log_action

from .notification_service import create_teacher_notification


def create_assignment(request, form):
    assignment = form.save(commit=False)
    assignment.teacher = request.user
    assignment.save()
    log_action(
        request,
        action_type="teacher.assignment.create",
        object_type="TeacherAssignment",
        object_id=assignment.pk,
        description=f"Teacher created assignment '{assignment}'",
        metadata={"course_id": assignment.course_id},
    )
    return assignment


def save_submission(request, form, assignment):
    submission = form.save(commit=False)
    submission.assignment = assignment
    submission.student = request.user
    submission.status = "submitted"
    submission.save()
    create_teacher_notification(
        teacher=assignment.teacher,
        actor=request.user,
        event_type=C.TEACHER_ASSIGNMENT_SUBMITTED,
        payload={"assignment_id": assignment.pk, "student_id": request.user.pk},
    )
    return submission


def review_submission(request, form):
    submission = form.save(commit=False)
    submission.reviewed_at = timezone.now()
    if submission.status == "submitted":
        submission.status = "reviewed"
    submission.save()
    log_action(
        request,
        action_type="teacher.assignment.review",
        target_user=submission.student,
        object_type="StudentAssignmentSubmission",
        object_id=submission.pk,
        description=f"Teacher reviewed assignment submission #{submission.pk}",
        metadata={"assignment_id": submission.assignment_id, "score": submission.score},
    )
    return submission

