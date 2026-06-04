from __future__ import annotations

from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command

from courses.models import Course, CourseLevel
from payments.models import PaymentSubmission
from platform_admin import permissions as perms


def png_bytes() -> bytes:
    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (1, 1), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


class PlatformAdminTestMixin:
    def setUp(self):
        # LocMemCache is NOT reset between tests; the hand-rolled per-IP
        # rate-limit counters would otherwise leak across the suite and make
        # registration/login flows order-dependent (200 vs 302 flakes).
        cache.clear()
        call_command("seed_platform_roles", verbosity=0)
        self.User = get_user_model()
        self.student = self.User.objects.create_user(
            username="student@example.com",
            email="student@example.com",
            password="pw",
        )
        self.student.profile.full_name = "Student One"
        self.student.profile.role = "student"
        self.student.profile.preferred_language = "ar"
        self.student.profile.cefr_level = "A1"
        self.student.profile.save()

        self.super_admin = self.make_user("super@example.com", is_staff=True, is_superuser=True)
        self.platform_admin = self.make_role_user("platform@example.com", perms.GROUP_PLATFORM_ADMIN)
        self.academic_admin = self.make_role_user("academic@example.com", perms.GROUP_ACADEMIC_ADMIN)
        self.teacher = self.make_role_user("teacher@example.com", perms.GROUP_TEACHER)
        self.teacher2 = self.make_role_user("teacher2@example.com", perms.GROUP_TEACHER)
        self.finance_admin = self.make_role_user("finance@example.com", perms.GROUP_FINANCE_ADMIN)
        self.support_admin = self.make_role_user("support@example.com", perms.GROUP_SUPPORT_ADMIN)
        self.ai_admin = self.make_role_user("ai@example.com", perms.GROUP_AI_ADMIN)
        self.readonly_admin = self.make_role_user("readonly@example.com", perms.GROUP_READ_ONLY_ADMIN)

        self.level = CourseLevel.objects.create(code="A1", name="A1", order=1)
        self.course = Course.objects.create(
            title="Teacher Video Course",
            slug="teacher-video-course",
            level=self.level,
            teacher=self.teacher,
            created_by=self.teacher,
            status="pending_review",
        )
        self.other_course = Course.objects.create(
            title="Other Course",
            slug="other-course",
            level=self.level,
            teacher=self.teacher2,
            created_by=self.teacher2,
            status="published",
        )
        self.payment = PaymentSubmission.objects.create(
            user=self.student,
            plan="monthly",
            method="bankak",
            amount_sdg=30000,
            screenshot=SimpleUploadedFile("proof.png", png_bytes(), content_type="image/png"),
            status="pending",
        )

    def make_user(self, email, **kwargs):
        user = self.User.objects.create_user(username=email, email=email, password="pw", **kwargs)
        user.profile.role = "admin" if kwargs.get("is_staff") else "student"
        user.profile.save(update_fields=["role"])
        return user

    def make_role_user(self, email, group_name):
        user = self.make_user(email, is_staff=True)
        user.groups.add(Group.objects.get(name=group_name))
        return user
