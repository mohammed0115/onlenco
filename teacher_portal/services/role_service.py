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


_ADMIN_ROLES = {
    ROLE_TEACHER,
    ROLE_ACADEMIC_ADMIN,
    ROLE_FINANCE_ADMIN,
    ROLE_SUPPORT_ADMIN,
    ROLE_AI_ADMIN,
    ROLE_PLATFORM_ADMIN,
    ROLE_SUPER_ADMIN,
}
_ADMIN_ONLY_ROLES = _ADMIN_ROLES - {ROLE_TEACHER}


class RoleService:
    """Multi-role facade for Onlenco users.

    Roles are stored in two places:
      * ``Profile.role`` carries the legacy ``student`` / ``admin`` flag.
      * Django Groups carry teacher + admin capabilities (the 7 groups in
        ``ROLE_TO_GROUP``).

    Rules:
      * A user is a *student* only when ``profile.role == "student"`` AND
        they hold no admin-side Group. This prevents Admin+Teacher accounts
        from being treated as students (which would inflict onboarding,
        placement, and the student dashboard on them).
      * Admin+Teacher is the supported dual-role: same person manages the
        platform and authors courses.
      * Student+Teacher is *not* automatic — it only happens for accounts
        explicitly marked ``profile.role == "student"`` AND added to the
        Teacher group.
    """

    @staticmethod
    def _has_admin_group(user) -> bool:
        if getattr(user, "is_superuser", False):
            return True
        admin_group_names = [ROLE_TO_GROUP[r] for r in _ADMIN_ONLY_ROLES if r in ROLE_TO_GROUP]
        return user.groups.filter(name__in=admin_group_names).exists()

    @staticmethod
    def _has_staff_group(user) -> bool:
        """True for users in any admin role OR the teacher role."""
        if RoleService._has_admin_group(user):
            return True
        teacher_group = ROLE_TO_GROUP.get(ROLE_TEACHER)
        return bool(teacher_group) and user.groups.filter(name=teacher_group).exists()

    @staticmethod
    def user_has_role(user, role: str) -> bool:
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        if role == ROLE_STUDENT:
            profile = getattr(user, "profile", None)
            profile_is_student = profile is None or getattr(profile, "role", "student") == "student"
            if not profile_is_student:
                return False
            # Staff accounts (admin or teacher) are not auto-students.
            if RoleService._has_staff_group(user):
                return False
            return True
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

    # ------------------------------------------------------------------
    # Helpers for Admin+Teacher routing
    # ------------------------------------------------------------------

    @staticmethod
    def is_admin_user(user) -> bool:
        """True when the user holds any admin-side role (not just teacher)."""
        if user is None or not getattr(user, "is_authenticated", False):
            return False
        return RoleService._has_admin_group(user)

    @staticmethod
    def is_teacher_user(user) -> bool:
        return RoleService.user_has_role(user, ROLE_TEACHER)

    @staticmethod
    def can_access_control_center(user) -> bool:
        return RoleService.is_admin_user(user)

    @staticmethod
    def can_access_teacher_portal(user) -> bool:
        return RoleService.is_teacher_user(user) or RoleService.is_admin_user(user)

    @staticmethod
    def get_default_landing_page(user) -> str:
        """URL name to send the user to right after login.

        Priority:
          1. Admin (any admin role)  → platform_admin dashboard router
          2. Teacher only            → teacher portal dashboard
          3. Student                 → student dashboard
          4. Fallback                → student dashboard
        """
        if RoleService.is_admin_user(user):
            try:
                from platform_admin.services.role_dashboards import dashboard_url_for
                return dashboard_url_for(user)
            except Exception:
                return "platform_admin:dashboard"
        if RoleService.is_teacher_user(user):
            return "teacher_portal:dashboard"
        return "dashboard"

    @staticmethod
    def available_staff_modes(user) -> list[dict]:
        """Modes shown in the staff switcher (Control Center / Teacher Portal).

        Student Mode is intentionally NOT included here — it lives in
        ``available_modes`` and is gated on the student role.
        """
        modes = []
        if RoleService.can_access_control_center(user):
            modes.append({
                "mode": "control",
                "en": "Control Center",
                "ar": "لوحة الإدارة",
                "url_name": "platform_admin:dashboard",
            })
        if RoleService.is_teacher_user(user):
            modes.append({
                "mode": "teacher",
                "en": "Teacher Portal",
                "ar": "لوحة الأستاذ",
                "url_name": "teacher_portal:dashboard",
            })
        return modes
