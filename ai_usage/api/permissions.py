"""Role helpers + DRF permissions for the AI-usage API."""
from __future__ import annotations

from django.conf import settings
from rest_framework.permissions import BasePermission

from .. import constants as C


def role_of(user) -> str:
    if user is None or not getattr(user, "is_authenticated", False):
        return C.ROLE_SYSTEM
    if getattr(user, "is_superuser", False):
        return C.ROLE_ADMIN
    profile = getattr(user, "profile", None)
    if profile is None:
        return C.ROLE_STUDENT
    try:
        if profile.is_admin:
            return C.ROLE_ADMIN
        if profile.is_teacher and not profile.is_student:
            return C.ROLE_TEACHER
    except Exception:
        pass
    return C.ROLE_STUDENT


def is_admin(user) -> bool:
    return role_of(user) == C.ROLE_ADMIN or getattr(user, "is_superuser", False)


def is_teacher(user) -> bool:
    return role_of(user) == C.ROLE_TEACHER


def student_can_view_cost() -> bool:
    return bool(getattr(settings, "AI_USAGE_STUDENT_CAN_VIEW_COST", False))


class IsAdminRole(BasePermission):
    message = "Admin access required."

    def has_permission(self, request, view):
        return bool(request.user and is_admin(request.user))
