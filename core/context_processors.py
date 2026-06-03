from django.conf import settings
from django.utils import translation

from .translations import DICT


# Default <title> / meta-description per language. Views may override
# either by passing `seo_title` / `seo_description` in the render context
# (a context value pushed after the processor wins).
_SEO_DEFAULT_TITLE = {
    "en": "Onlenco Academy — AI English Learning Platform for Sudan",
    "ar": "أكاديمية Onlenco — منصة تعلّم الإنجليزية بالذكاء الاصطناعي",
}
_SEO_DEFAULT_DESCRIPTION = {
    "en": (
        "Onlenco Academy is an AI-powered English learning platform built "
        "for Sudanese students: a smart placement test, an AI conversation "
        "tutor, speaking practice and a personalised daily plan — in Arabic "
        "and English."
    ),
    "ar": (
        "أكاديمية Onlenco منصة لتعلّم اللغة الإنجليزية بالذكاء الاصطناعي "
        "مصمّمة للطلاب السودانيين: اختبار تحديد مستوى ذكي، معلّم محادثة "
        "بالذكاء الاصطناعي، تدريب على المحادثة، وخطة يومية مخصّصة — "
        "بالعربية والإنجليزية."
    ),
}


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
        **_seo_context(request, lang),
    }


def _seo_context(request, lang: str) -> dict:
    """Canonical URL, hreflang alternates and SEO defaults.

    The site switches language by cookie (no `/ar/` `/en/` URL prefixes),
    so each language is given a stable, crawlable URL via `?hl=ar` /
    `?hl=en`. Every page therefore self-canonicalises *including* its
    `?hl=` parameter so the hreflang cluster is internally consistent.
    """
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    # Older tests (and any non-HTTP caller) hand us ``request=None``; treat
    # that as "root URL, no hl param" so the processor still returns the
    # full SEO context dict without exploding.
    path = getattr(request, "path", "/") if request is not None else "/"
    get_params = getattr(request, "GET", {}) if request is not None else {}
    base = f"{site_url}{path}"
    hl = (get_params.get("hl") or "").strip().lower() if hasattr(get_params, "get") else ""
    canonical = f"{base}?hl={hl}" if hl in ("ar", "en") else base
    return {
        "SITE_URL": site_url,
        "canonical_url": canonical,
        "hreflang_default": base,
        "hreflang_ar": f"{base}?hl=ar",
        "hreflang_en": f"{base}?hl=en",
        "og_locale": "ar_AR" if lang == "ar" else "en_US",
        "seo_title": _SEO_DEFAULT_TITLE[lang],
        "seo_description": _SEO_DEFAULT_DESCRIPTION[lang],
        # Search Console verification token + GA4 id (both empty unless set in
        # the environment, so nothing renders/loads by default).
        "google_site_verification": getattr(settings, "GOOGLE_SITE_VERIFICATION", ""),
        "google_analytics_id": getattr(settings, "GOOGLE_ANALYTICS_ID", ""),
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
