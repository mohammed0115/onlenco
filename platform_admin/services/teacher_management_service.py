from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

from courses.models import Course, CourseEnrollment, Lesson
from platform_admin.permissions import GROUP_TEACHER
from platform_admin.services.audit_log_service import log_action
from teacher_portal.models import TeacherProfile
from teacher_portal.services.role_service import ROLE_TEACHER, RoleService


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
