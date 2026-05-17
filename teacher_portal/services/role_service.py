from __future__ import annotations

from django.contrib.auth.models import Group

from platform_admin import permissions as platform_perms


ROLE_STUDENT = "student"
ROLE_TEACHER = "teacher"
ROLE_ACADEMIC_ADMIN = "academic_admin"
ROLE_FINANCE_ADMIN = "finance_admin"
ROLE_SUPPORT_ADMIN = "support_admin"
ROLE_AI_ADMIN = "ai_admin"
ROLE_PLATFORM_ADMIN = "platform_admin"
ROLE_SUPER_ADMIN = "super_admin"

ROLE_TO_GROUP = {
    ROLE_TEACHER: platform_perms.GROUP_TEACHER,
    ROLE_ACADEMIC_ADMIN: platform_perms.GROUP_ACADEMIC_ADMIN,
    ROLE_FINANCE_ADMIN: platform_perms.GROUP_FINANCE_ADMIN,
    ROLE_SUPPORT_ADMIN: platform_perms.GROUP_SUPPORT_ADMIN,
    ROLE_AI_ADMIN: platform_perms.GROUP_AI_ADMIN,
    ROLE_PLATFORM_ADMIN: platform_perms.GROUP_PLATFORM_ADMIN,
    ROLE_SUPER_ADMIN: platform_perms.GROUP_SUPER_ADMIN,
}

ROLE_LABELS = {
    ROLE_STUDENT: {"en": "Student Mode", "ar": "وضع الطالب"},
    ROLE_TEACHER: {"en": "Teacher Mode", "ar": "وضع الأستاذ"},
}


class RoleService:
    """Multi-role facade for Onlenco users.

    The existing `Profile.role` remains the student/admin legacy flag.
    Staff/admin/teacher capabilities live in Django Groups. Combining the
    two lets one account be both a learner and an instructor.
    """

    @staticmethod
    def user_has_role(user, role: str) -> bool:
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        if role == ROLE_STUDENT:
            profile = getattr(user, "profile", None)
            return profile is None or getattr(profile, "role", "student") == "student"
        if role == ROLE_SUPER_ADMIN and getattr(user, "is_superuser", False):
            return True
        group_name = ROLE_TO_GROUP.get(role)
        if not group_name:
            return False
        if getattr(user, "is_superuser", False):
            return True
        return user.groups.filter(name=group_name).exists()

    @staticmethod
    def get_user_roles(user) -> list[str]:
        if user is None or not getattr(user, "is_authenticated", False):
            return []
        roles: list[str] = []
        if RoleService.user_has_role(user, ROLE_STUDENT):
            roles.append(ROLE_STUDENT)
        for role in [
            ROLE_TEACHER,
            ROLE_ACADEMIC_ADMIN,
            ROLE_FINANCE_ADMIN,
            ROLE_SUPPORT_ADMIN,
            ROLE_AI_ADMIN,
            ROLE_PLATFORM_ADMIN,
            ROLE_SUPER_ADMIN,
        ]:
            if RoleService.user_has_role(user, role):
                roles.append(role)
        return roles

    @staticmethod
    def assign_role(user, role: str) -> None:
        group_name = ROLE_TO_GROUP.get(role)
        if not group_name:
            return
        group, _created = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)

    @staticmethod
    def remove_role(user, role: str) -> None:
        group_name = ROLE_TO_GROUP.get(role)
        if not group_name:
            return
        groups = list(Group.objects.filter(name=group_name))
        if groups:
            user.groups.remove(*groups)

    @staticmethod
    def set_active_role(request, role: str) -> bool:
        if not RoleService.user_has_role(request.user, role):
            return False
        request.session["active_role"] = role
        return True

    @staticmethod
    def get_active_role(request) -> str:
        role = request.session.get("active_role")
        if role and RoleService.user_has_role(request.user, role):
            return role
        if RoleService.user_has_role(request.user, ROLE_STUDENT):
            return ROLE_STUDENT
        roles = RoleService.get_user_roles(request.user)
        return roles[0] if roles else ROLE_STUDENT

    @staticmethod
    def available_modes(user) -> list[dict]:
        modes = []
        for role in [ROLE_STUDENT, ROLE_TEACHER]:
            if RoleService.user_has_role(user, role):
                modes.append({"role": role, **ROLE_LABELS[role]})
        return modes

    @staticmethod
    def is_multi_mode_user(user) -> bool:
        return (
            RoleService.user_has_role(user, ROLE_STUDENT)
            and RoleService.user_has_role(user, ROLE_TEACHER)
        )
