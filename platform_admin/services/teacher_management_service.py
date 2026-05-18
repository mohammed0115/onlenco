from __future__ import annotations

import logging
import secrets
import string

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.template.loader import render_to_string

from courses.models import Course, CourseEnrollment, Lesson
from platform_admin.permissions import GROUP_TEACHER
from platform_admin.services.audit_log_service import log_action
from teacher_portal.models import TeacherProfile
from teacher_portal.services.role_service import ROLE_TEACHER, RoleService


logger = logging.getLogger(__name__)

TEMP_PASSWORD_LENGTH = 14
_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%&*"


def teacher_queryset(params=None):
    User = get_user_model()
    qs = (
        User.objects.filter(Q(groups__name=GROUP_TEACHER) | Q(taught_courses__isnull=False) | Q(created_courses__isnull=False))
        .distinct()
        .annotate(
            courses_count=Count("taught_courses", distinct=True),
            created_courses_count=Count("created_courses", distinct=True),
        )
        .order_by("email", "username")
    )
    q = ((params or {}).get("q") or "").strip()
    if q:
        qs = qs.filter(Q(email__icontains=q) | Q(username__icontains=q) | Q(profile__full_name__icontains=q))
    return qs


def teacher_detail_context(teacher) -> dict:
    courses = (
        Course.objects.filter(Q(teacher=teacher) | Q(created_by=teacher))
        .select_related("level")
        .prefetch_related("lessons")
        .distinct()
    )
    lessons = Lesson.objects.filter(Q(course__teacher=teacher) | Q(created_by=teacher)).select_related("course")[:50]
    enrollments = CourseEnrollment.objects.filter(course__in=courses).select_related("user", "course")[:100]
    return {
        "teacher": teacher,
        "courses": courses,
        "lessons": lessons,
        "enrollments": enrollments,
        "stats": {
            "courses": courses.count(),
            "published": courses.filter(status="published").count(),
            "pending": courses.filter(status="pending_review").count(),
            "students": enrollments.values("user_id").distinct().count(),
        },
    }


def assign_course_to_teacher(request, teacher, course):
    old_teacher_id = course.teacher_id
    course.teacher = teacher
    if course.created_by_id is None:
        course.created_by = teacher
    course.save(update_fields=["teacher", "created_by", "updated_at"])
    log_action(
        request,
        action_type="teacher.assign_course",
        target_user=teacher,
        object_type="Course",
        object_id=course.pk,
        description=f"Assigned course '{course.title}' to teacher {teacher.email or teacher.username}",
        metadata={"old_teacher_id": old_teacher_id, "new_teacher_id": teacher.pk},
    )


def deactivate_teacher(request, teacher):
    teacher.is_active = False
    teacher.save(update_fields=["is_active"])
    TeacherProfile.objects.update_or_create(user=teacher, defaults={"is_active": False})
    log_action(
        request,
        action_type="teacher.deactivate",
        target_user=teacher,
        object_type="auth.User",
        object_id=teacher.pk,
        description=f"Deactivated teacher {teacher.email or teacher.username}",
    )


def assign_teacher_role(request, teacher):
    RoleService.assign_role(teacher, ROLE_TEACHER)
    TeacherProfile.objects.get_or_create(user=teacher)
    log_action(
        request,
        action_type="teacher.role.assign",
        target_user=teacher,
        object_type="auth.User",
        object_id=teacher.pk,
        description=f"Assigned teacher role to {teacher.email or teacher.username}",
    )


def remove_teacher_role(request, teacher):
    RoleService.remove_role(teacher, ROLE_TEACHER)
    TeacherProfile.objects.filter(user=teacher).update(is_active=False)
    log_action(
        request,
        action_type="teacher.role.remove",
        target_user=teacher,
        object_type="auth.User",
        object_id=teacher.pk,
        description=f"Removed teacher role from {teacher.email or teacher.username}",
    )


# ---------------------------------------------------------------------------
# Admin-created teacher onboarding
# ---------------------------------------------------------------------------

def generate_temporary_password(length: int = TEMP_PASSWORD_LENGTH) -> str:
    """Cryptographically secure temporary password with mixed character classes."""
    return "".join(secrets.choice(_PASSWORD_ALPHABET) for _ in range(length))


@transaction.atomic
def register_teacher(request, *, first_name: str, last_name: str, email: str) -> tuple:
    """Create a teacher account with a one-shot temp password.

    Returns ``(user, temp_password)``. The caller is responsible for the
    email delivery side-effect — we keep them separate so failed delivery
    does not roll back the user creation.
    """
    User = get_user_model()
    email = email.strip().lower()
    temp_password = generate_temporary_password()

    user = User.objects.create_user(
        username=email,
        email=email,
        password=temp_password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        is_active=True,
        is_staff=True,
    )
    profile = user.profile
    profile.full_name = f"{user.first_name} {user.last_name}".strip()
    profile.role = "student"  # legacy field; RoleService treats teacher group as non-student
    profile.email_verified = True  # admin-vouched
    profile.onboarding_completed = True  # teachers skip the student onboarding flow
    profile.must_change_password = True
    profile.save(update_fields=[
        "full_name", "role", "email_verified",
        "onboarding_completed", "must_change_password",
    ])
    RoleService.assign_role(user, ROLE_TEACHER)
    TeacherProfile.objects.get_or_create(user=user)

    log_action(
        request,
        action_type="teacher.register",
        target_user=user,
        object_type="auth.User",
        object_id=user.pk,
        description=f"Registered teacher {email}",
        metadata={"by_admin": getattr(request.user, "email", None) or getattr(request.user, "username", None)},
    )
    return user, temp_password


def send_teacher_welcome_email(user, temp_password: str) -> bool:
    """Email the teacher their temporary password.

    Uses the project's email service. Returns True on success."""
    try:
        from notifications.services.email_service import EmailService
    except Exception:
        logger.warning("teacher welcome: EmailService unavailable", exc_info=True)
        return False
    try:
        login_url = "/auth/"
        context = {
            "user": user,
            "first_name": user.first_name or user.email,
            "email": user.email,
            "temp_password": temp_password,
            "login_url": login_url,
        }
        subject = "Onlenco — Your teacher account is ready"
        html = render_to_string("platform_admin/emails/teacher_welcome.html", context)
        text = render_to_string("platform_admin/emails/teacher_welcome.txt", context)
        email_service = EmailService()
        result = email_service.send_email(
            recipient_email=user.email,
            subject=subject,
            html_body=html,
            text_body=text,
        )
        return bool(result and getattr(result, "success", True))
    except Exception:
        logger.exception("teacher welcome email failed for %s", user.email)
        return False
