"""Role + object-level permission helpers.

Group names are constants so admin / tests / seeders agree on spelling.
The functions here are the *single source of truth* for "can this user
do X to this object?" — admin classes call into them rather than
re-implementing the rule.
"""
from __future__ import annotations

from typing import Optional

# Group names — also seeded by `seed_role_groups` management command.
GROUP_SUPER_ADMIN     = "Super Admin"
GROUP_ACADEMIC_ADMIN  = "Academic Admin"
GROUP_TEACHER         = "Teacher"
GROUP_FINANCE_ADMIN   = "Finance Admin"
GROUP_SUPPORT_ADMIN   = "Support Admin"

ALL_GROUPS = [
    GROUP_SUPER_ADMIN, GROUP_ACADEMIC_ADMIN, GROUP_TEACHER,
    GROUP_FINANCE_ADMIN, GROUP_SUPPORT_ADMIN,
]


def _user_in_group(user, group_name: str) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True   # superusers transcend groups
    return user.groups.filter(name=group_name).exists()


def is_super_admin(user) -> bool:
    return getattr(user, "is_superuser", False) or _user_in_group(user, GROUP_SUPER_ADMIN)


def is_academic_admin(user) -> bool:
    return is_super_admin(user) or _user_in_group(user, GROUP_ACADEMIC_ADMIN)


def is_teacher(user) -> bool:
    return _user_in_group(user, GROUP_TEACHER)


def is_finance_admin(user) -> bool:
    return is_super_admin(user) or _user_in_group(user, GROUP_FINANCE_ADMIN)


def is_support_admin(user) -> bool:
    return is_super_admin(user) or _user_in_group(user, GROUP_SUPPORT_ADMIN)


# ---------------------------------------------------------------------------
# Object-level rules
# ---------------------------------------------------------------------------

def can_edit_course(user, course) -> bool:
    """Academic Admin → any course. Teacher → only their own courses."""
    if is_academic_admin(user):
        return True
    if is_teacher(user) and course is not None:
        return course.created_by_id == getattr(user, "id", None) \
               or course.teacher_id == getattr(user, "id", None)
    return False


def can_publish_course(user, course=None) -> bool:
    """Only Academic Admin (or Super Admin) can flip a course to
    `published`. Teachers can submit for review; they cannot publish."""
    return is_academic_admin(user)


def can_edit_lesson(user, lesson) -> bool:
    if is_academic_admin(user):
        return True
    if is_teacher(user) and lesson is not None:
        # Teacher can edit lessons in courses they own, OR lessons they
        # personally created.
        course = lesson.course
        return (
            course.created_by_id == getattr(user, "id", None)
            or course.teacher_id  == getattr(user, "id", None)
            or lesson.created_by_id == getattr(user, "id", None)
        )
    return False


def can_review_content(user) -> bool:
    """Approve / reject content submitted for review."""
    return is_academic_admin(user)


def filter_courses_for(user, qs):
    """Narrow a Course queryset to what `user` is allowed to see/edit
    inside the admin. Used by `ModelAdmin.get_queryset`."""
    if is_academic_admin(user):
        return qs
    if is_teacher(user):
        from django.db.models import Q
        return qs.filter(Q(created_by=user) | Q(teacher=user))
    return qs.none()


def filter_lessons_for(user, qs):
    if is_academic_admin(user):
        return qs
    if is_teacher(user):
        from django.db.models import Q
        return qs.filter(
            Q(created_by=user) | Q(course__created_by=user) | Q(course__teacher=user)
        )
    return qs.none()
