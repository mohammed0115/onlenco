from django.utils import translation

from .translations import DICT


def site_context(request):
    """Adds language helpers and the translation dictionary to every template.

    We use a flat dict keyed by tokens like `hero.title1` with `en` / `ar`
    values. Exposes a `t(key)` helper plus `lang` / `dir` flags for
    templates.
    """
    lang = translation.get_language() or "en"
    if lang.startswith("ar"):
        lang = "ar"
    else:
        lang = "en"

    def t(key):
        entry = DICT.get(key)
        if not entry:
            return key
        return entry.get(lang) or entry.get("en") or key

    return {
        "lang": lang,
        "dir": "rtl" if lang == "ar" else "ltr",
        "t": t,
        "T": DICT,  # raw dict for advanced lookups in templates
        "can_access_control_center": _can_access_control_center(request),
        "can_access_teacher_portal": _can_access_teacher_portal(request),
        "show_student_mode": _show_student_mode(request),
        "primary_role_label": _primary_role_label(request, lang),
    }


def _show_student_mode(request) -> bool:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    try:
        from teacher_portal.services.role_service import ROLE_STUDENT, RoleService
        return RoleService.user_has_role(user, ROLE_STUDENT)
    except Exception:
        return False


def _primary_role_label(request, lang: str) -> str:
    """Topbar label for the profile pill: shows the admin/teacher role
    instead of a generic 'My Account' for staff accounts."""
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return ""
    try:
        from platform_admin.permissions import (
            GROUP_SUPER_ADMIN, GROUP_PLATFORM_ADMIN, GROUP_ACADEMIC_ADMIN,
            GROUP_FINANCE_ADMIN, GROUP_SUPPORT_ADMIN, GROUP_AI_ADMIN,
            GROUP_READ_ONLY_ADMIN, GROUP_TEACHER, user_role_names,
        )
    except Exception:
        return ""
    role_labels = {
        GROUP_SUPER_ADMIN: ("Super Admin", "مدير عام"),
        GROUP_PLATFORM_ADMIN: ("Platform Admin", "مدير المنصة"),
        GROUP_ACADEMIC_ADMIN: ("Academic Admin", "مدير أكاديمي"),
        GROUP_FINANCE_ADMIN: ("Finance Admin", "مدير مالي"),
        GROUP_SUPPORT_ADMIN: ("Support Admin", "مدير الدعم"),
        GROUP_AI_ADMIN: ("AI Admin", "مدير AI"),
        GROUP_READ_ONLY_ADMIN: ("Read-only", "قراءة فقط"),
        GROUP_TEACHER: ("Teacher", "أستاذ"),
    }
    priority = [
        GROUP_SUPER_ADMIN, GROUP_PLATFORM_ADMIN, GROUP_ACADEMIC_ADMIN,
        GROUP_FINANCE_ADMIN, GROUP_SUPPORT_ADMIN, GROUP_AI_ADMIN,
        GROUP_READ_ONLY_ADMIN, GROUP_TEACHER,
    ]
    if getattr(user, "is_superuser", False):
        return role_labels[GROUP_SUPER_ADMIN][1 if lang == "ar" else 0]
    roles = user_role_names(user)
    for role in priority:
        if role in roles:
            return role_labels[role][1 if lang == "ar" else 0]
    return ""


def _can_access_control_center(request) -> bool:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    try:
        from teacher_portal.services.role_service import RoleService
        return RoleService.can_access_control_center(user)
    except Exception:
        return False


def _can_access_teacher_portal(request) -> bool:
    user = getattr(request, "user", None)
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    try:
        from teacher_portal.services.role_service import RoleService
        return RoleService.is_teacher_user(user)
    except Exception:
        return False
