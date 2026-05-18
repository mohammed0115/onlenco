from __future__ import annotations

from django.contrib.auth.models import Group
from django.db.models import Q


GROUP_SUPER_ADMIN = "Super Admin"
GROUP_PLATFORM_ADMIN = "Platform Admin"
GROUP_ACADEMIC_ADMIN = "Academic Admin"
GROUP_TEACHER = "Teacher"
GROUP_FINANCE_ADMIN = "Finance Admin"
GROUP_SUPPORT_ADMIN = "Support Admin"
GROUP_AI_ADMIN = "AI Admin"
GROUP_READ_ONLY_ADMIN = "Read-only Admin"

ALL_ROLE_GROUPS = [
    GROUP_SUPER_ADMIN,
    GROUP_PLATFORM_ADMIN,
    GROUP_ACADEMIC_ADMIN,
    GROUP_TEACHER,
    GROUP_FINANCE_ADMIN,
    GROUP_SUPPORT_ADMIN,
    GROUP_AI_ADMIN,
    GROUP_READ_ONLY_ADMIN,
]

CAP_DASHBOARD = "dashboard.view"
CAP_STUDENTS_VIEW = "students.view"
CAP_STUDENTS_MANAGE = "students.manage"
CAP_TEACHERS_VIEW = "teachers.view"
CAP_TEACHERS_MANAGE = "teachers.manage"
CAP_COURSES_VIEW = "courses.view"
CAP_COURSES_MANAGE = "courses.manage"
CAP_COURSES_REVIEW = "courses.review"
CAP_PAYMENTS_VIEW = "payments.view"
CAP_PAYMENTS_MANAGE = "payments.manage"
CAP_AI_VIEW = "ai.view"
CAP_AI_MANAGE = "ai.manage"
CAP_ANALYTICS_VIEW = "analytics.view"
CAP_NOTIFICATIONS_MANAGE = "notifications.manage"
CAP_GAMIFICATION_MANAGE = "gamification.manage"
CAP_SETTINGS_VIEW = "settings.view"
CAP_SETTINGS_MANAGE = "settings.manage"
CAP_PLANS_VIEW = "plans.view"
CAP_PLANS_MANAGE = "plans.manage"
CAP_AUDIT_VIEW = "audit.view"
CAP_EXPORT = "data.export"

VIEW_CAPS = {
    CAP_DASHBOARD,
    CAP_STUDENTS_VIEW,
    CAP_TEACHERS_VIEW,
    CAP_COURSES_VIEW,
    CAP_PAYMENTS_VIEW,
    CAP_AI_VIEW,
    CAP_ANALYTICS_VIEW,
    CAP_SETTINGS_VIEW,
    CAP_PLANS_VIEW,
    CAP_AUDIT_VIEW,
}

ROLE_CAPABILITIES = {
    GROUP_SUPER_ADMIN: {"*"},
    GROUP_PLATFORM_ADMIN: {"*"},
    GROUP_ACADEMIC_ADMIN: {
        CAP_DASHBOARD,
        CAP_STUDENTS_VIEW,
        CAP_STUDENTS_MANAGE,
        CAP_TEACHERS_VIEW,
        CAP_TEACHERS_MANAGE,
        CAP_COURSES_VIEW,
        CAP_COURSES_MANAGE,
        CAP_COURSES_REVIEW,
        CAP_ANALYTICS_VIEW,
        CAP_AUDIT_VIEW,
        CAP_EXPORT,
    },
    GROUP_TEACHER: {
        CAP_DASHBOARD,
        CAP_STUDENTS_VIEW,
        CAP_TEACHERS_VIEW,
        CAP_COURSES_VIEW,
        CAP_COURSES_MANAGE,
    },
    GROUP_FINANCE_ADMIN: {
        CAP_DASHBOARD,
        CAP_STUDENTS_VIEW,
        CAP_PAYMENTS_VIEW,
        CAP_PAYMENTS_MANAGE,
        CAP_PLANS_VIEW,
        CAP_PLANS_MANAGE,
        CAP_ANALYTICS_VIEW,
        CAP_AUDIT_VIEW,
        CAP_EXPORT,
    },
    GROUP_SUPPORT_ADMIN: {
        CAP_DASHBOARD,
        CAP_STUDENTS_VIEW,
        CAP_NOTIFICATIONS_MANAGE,
        CAP_AUDIT_VIEW,
    },
    GROUP_AI_ADMIN: {
        CAP_DASHBOARD,
        CAP_AI_VIEW,
        CAP_AI_MANAGE,
        CAP_ANALYTICS_VIEW,
        CAP_AUDIT_VIEW,
        CAP_EXPORT,
    },
    GROUP_READ_ONLY_ADMIN: set(VIEW_CAPS),
}


def ensure_role_groups() -> list[Group]:
    groups = []
    for name in ALL_ROLE_GROUPS:
        group, _created = Group.objects.get_or_create(name=name)
        groups.append(group)
    return groups


def user_role_names(user) -> set[str]:
    if user is None or not getattr(user, "is_authenticated", False):
        return set()
    names = set(user.groups.filter(name__in=ALL_ROLE_GROUPS).values_list("name", flat=True))
    if getattr(user, "is_superuser", False):
        names.add(GROUP_SUPER_ADMIN)
    return names


def is_control_user(user) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    if user_role_names(user):
        return True
    profile = getattr(user, "profile", None)
    if profile is not None and getattr(profile, "role", "") == "admin":
        return True
    return bool(getattr(user, "is_staff", False) and user.has_perm("auth.view_user"))


def has_role(user, *role_names: str) -> bool:
    if getattr(user, "is_superuser", False):
        return True
    return bool(user_role_names(user).intersection(role_names))


def is_read_only(user) -> bool:
    roles = user_role_names(user)
    if GROUP_READ_ONLY_ADMIN not in roles:
        return False
    return not roles.intersection({
        GROUP_SUPER_ADMIN,
        GROUP_PLATFORM_ADMIN,
        GROUP_ACADEMIC_ADMIN,
        GROUP_TEACHER,
        GROUP_FINANCE_ADMIN,
        GROUP_SUPPORT_ADMIN,
        GROUP_AI_ADMIN,
    })


def has_capability(user, capability: str) -> bool:
    if not is_control_user(user):
        return False
    if getattr(user, "is_superuser", False):
        return True
    roles = user_role_names(user)
    if not roles:
        profile = getattr(user, "profile", None)
        if profile is not None and getattr(profile, "role", "") == "admin":
            roles = {GROUP_PLATFORM_ADMIN}
    for role in roles:
        caps = ROLE_CAPABILITIES.get(role, set())
        if "*" in caps or capability in caps:
            return True
        if role == GROUP_READ_ONLY_ADMIN and capability in VIEW_CAPS:
            return True
    return False


def can_mutate(user, capability: str) -> bool:
    return has_capability(user, capability) and not is_read_only(user)


def is_teacher(user) -> bool:
    return has_role(user, GROUP_TEACHER)


def can_view_payment(user) -> bool:
    return has_capability(user, CAP_PAYMENTS_VIEW)


def can_manage_payment(user) -> bool:
    return can_mutate(user, CAP_PAYMENTS_MANAGE)


def can_view_ai(user) -> bool:
    return has_capability(user, CAP_AI_VIEW)


def can_review_course(user) -> bool:
    return can_mutate(user, CAP_COURSES_REVIEW)


def can_manage_course(user, course=None) -> bool:
    if not can_mutate(user, CAP_COURSES_MANAGE):
        return False
    if has_role(user, GROUP_ACADEMIC_ADMIN, GROUP_PLATFORM_ADMIN, GROUP_SUPER_ADMIN):
        return True
    if is_teacher(user) and course is not None:
        return course.teacher_id == getattr(user, "id", None) or course.created_by_id == getattr(user, "id", None)
    return is_teacher(user) and course is None


def courses_for_user(user, qs):
    if has_role(user, GROUP_ACADEMIC_ADMIN, GROUP_PLATFORM_ADMIN, GROUP_SUPER_ADMIN) or has_capability(user, CAP_COURSES_REVIEW):
        return qs
    if is_teacher(user):
        return qs.filter(Q(teacher=user) | Q(created_by=user))
    if has_capability(user, CAP_COURSES_VIEW):
        return qs
    return qs.none()


def students_for_user(user, qs):
    if not has_capability(user, CAP_STUDENTS_VIEW):
        return qs.none()
    if is_teacher(user) and not has_role(user, GROUP_ACADEMIC_ADMIN, GROUP_PLATFORM_ADMIN, GROUP_SUPER_ADMIN):
        return qs.filter(course_enrollments__course__in=courses_for_user(user, _course_qs())).distinct()
    return qs


def _course_qs():
    from courses.models import Course
    return Course.objects.all()


def can_view_student(user, student) -> bool:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return students_for_user(user, User.objects.filter(pk=getattr(student, "pk", None))).exists()


def nav_items_for(user) -> list[dict]:
    items = [
        (CAP_DASHBOARD, "Dashboard", "لوحة التحكم", "layout-dashboard", "platform_admin:dashboard"),
        (CAP_STUDENTS_VIEW, "Students", "الطلاب", "users", "platform_admin:students"),
        (CAP_TEACHERS_VIEW, "Teachers", "المعلمون", "graduation-cap", "platform_admin:teachers"),
        (CAP_COURSES_VIEW, "Courses", "الكورسات", "book-open", "platform_admin:courses"),
        (CAP_PAYMENTS_VIEW, "Payments", "المدفوعات", "wallet", "platform_admin:payments"),
        (CAP_PLANS_VIEW, "Plans", "الخطط", "package", "platform_admin:plans"),
        (CAP_SETTINGS_VIEW, "Voices & Avatars", "الأصوات والصور", "mic", "platform_admin:voices"),
        (CAP_AI_VIEW, "AI Monitor", "مراقبة AI", "bot", "platform_admin:ai_overview"),
        (CAP_ANALYTICS_VIEW, "Analytics", "التحليلات", "bar-chart-3", "platform_admin:analytics"),
        (CAP_GAMIFICATION_MANAGE, "Game Sounds", "أصوات اللعبة", "music", "platform_admin:gamification_sounds"),
        (CAP_SETTINGS_VIEW, "Settings", "الإعدادات", "settings", "platform_admin:settings_roles"),
        (CAP_AUDIT_VIEW, "Audit Logs", "سجل العمليات", "shield-check", "platform_admin:audit_logs"),
    ]
    return [
        {"label_en": en, "label_ar": ar, "icon": icon, "url_name": url_name}
        for cap, en, ar, icon, url_name in items
        if has_capability(user, cap)
    ]
