from __future__ import annotations

from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand

from platform_admin.permissions import (
    ALL_ROLE_GROUPS,
    GROUP_ACADEMIC_ADMIN,
    GROUP_AI_ADMIN,
    GROUP_FINANCE_ADMIN,
    GROUP_PLATFORM_ADMIN,
    GROUP_READ_ONLY_ADMIN,
    GROUP_SUPPORT_ADMIN,
    GROUP_TEACHER,
    ensure_role_groups,
)


class Command(BaseCommand):
    help = "Seed Onlenco Control Center role groups."

    def handle(self, *args, **options):
        groups = {group.name: group for group in ensure_role_groups()}

        # Keep Django model permissions useful for fallback admin/detail
        # checks, while platform_admin.permissions remains the control
        # center's source of truth.
        view_perms = Permission.objects.filter(codename__startswith="view_")
        course_perms = Permission.objects.filter(content_type__app_label="courses")
        payment_perms = Permission.objects.filter(content_type__app_label="payments")
        ai_perms = Permission.objects.filter(content_type__app_label__in=["ai_engine", "ai_training", "tutor"])
        account_view_perms = Permission.objects.filter(content_type__app_label__in=["accounts", "auth"], codename__startswith="view_")

        groups[GROUP_PLATFORM_ADMIN].permissions.set(Permission.objects.all())
        groups[GROUP_ACADEMIC_ADMIN].permissions.set(course_perms | account_view_perms)
        groups[GROUP_TEACHER].permissions.set(
            course_perms.filter(codename__startswith="add_")
            | course_perms.filter(codename__startswith="change_")
            | course_perms.filter(codename__startswith="view_")
        )
        groups[GROUP_FINANCE_ADMIN].permissions.set(payment_perms | account_view_perms)
        groups[GROUP_SUPPORT_ADMIN].permissions.set(view_perms.filter(content_type__app_label__in=["accounts", "auth", "courses", "notifications"]))
        groups[GROUP_AI_ADMIN].permissions.set(ai_perms | view_perms.filter(content_type__app_label="accounts"))
        groups[GROUP_READ_ONLY_ADMIN].permissions.set(view_perms)

        # Super Admin is intentionally empty: real super admins should use
        # is_superuser=True. The group exists for display/assignment clarity.
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(ALL_ROLE_GROUPS)} Onlenco platform role groups."))
