from __future__ import annotations

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden

from courses.models import Course, CourseEnrollment, Lesson
from platform_admin import permissions as platform_perms

from .services.role_service import ROLE_TEACHER, RoleService


def teacher_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not RoleService.user_has_role(request.user, ROLE_TEACHER):
            return HttpResponseForbidden("Teacher access required")
        request.session["active_role"] = ROLE_TEACHER
        return view_func(request, *args, **kwargs)

    return wrapper


def academic_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not platform_perms.has_role(
            request.user,
            platform_perms.GROUP_ACADEMIC_ADMIN,
            platform_perms.GROUP_PLATFORM_ADMIN,
            platform_perms.GROUP_SUPER_ADMIN,
        ):
            return HttpResponseForbidden("Academic admin access required")
        return view_func(request, *args, **kwargs)

    return wrapper


def teacher_course_queryset(user):
    if platform_perms.has_role(
        user,
        platform_perms.GROUP_ACADEMIC_ADMIN,
        platform_perms.GROUP_PLATFORM_ADMIN,
        platform_perms.GROUP_SUPER_ADMIN,
    ):
        return Course.objects.all()
    if not RoleService.user_has_role(user, ROLE_TEACHER):
        return Course.objects.none()
    return Course.objects.filter(Q(teacher=user) | Q(created_by=user)).distinct()


def teacher_lesson_queryset(user):
    if platform_perms.has_role(
        user,
        platform_perms.GROUP_ACADEMIC_ADMIN,
        platform_perms.GROUP_PLATFORM_ADMIN,
        platform_perms.GROUP_SUPER_ADMIN,
    ):
        return Lesson.objects.all()
    if not RoleService.user_has_role(user, ROLE_TEACHER):
        return Lesson.objects.none()
    return Lesson.objects.filter(
        Q(created_by=user) | Q(course__teacher=user) | Q(course__created_by=user)
    ).distinct()


def teacher_owns_course(user, course) -> bool:
    return teacher_course_queryset(user).filter(pk=getattr(course, "pk", None)).exists()


def teacher_can_edit_course(user, course) -> bool:
    if platform_perms.has_role(
        user,
        platform_perms.GROUP_ACADEMIC_ADMIN,
        platform_perms.GROUP_PLATFORM_ADMIN,
        platform_perms.GROUP_SUPER_ADMIN,
    ):
        return True
    return teacher_owns_course(user, course) and course.status in {"draft", "rejected"}


def teacher_can_edit_lesson(user, lesson) -> bool:
    if platform_perms.has_role(
        user,
        platform_perms.GROUP_ACADEMIC_ADMIN,
        platform_perms.GROUP_PLATFORM_ADMIN,
        platform_perms.GROUP_SUPER_ADMIN,
    ):
        return True
    return (
        teacher_lesson_queryset(user).filter(pk=getattr(lesson, "pk", None)).exists()
        and lesson.status in {"draft", "rejected"}
    )


def students_for_teacher(user):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    courses = teacher_course_queryset(user)
    if not courses.exists():
        return User.objects.none()
    return User.objects.filter(course_enrollments__course__in=courses).distinct()


def teacher_can_view_student(user, student) -> bool:
    return students_for_teacher(user).filter(pk=getattr(student, "pk", None)).exists()


def student_is_enrolled(user, course) -> bool:
    return CourseEnrollment.objects.filter(user=user, course=course, status="active").exists()
