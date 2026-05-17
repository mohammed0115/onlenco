from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase

from courses.models import Course, CourseEnrollment, CourseLevel, CourseLessonProgress, Lesson
from payments.models import PaymentSubmission
from platform_admin import permissions as platform_perms


class TeacherPortalTestMixin(TestCase):
    def setUp(self):
        call_command("seed_platform_roles", verbosity=0)
        self.User = get_user_model()
        self.level = CourseLevel.objects.create(code="A1", name="A1", order=1)
        self.teacher = self.make_user("teacher@example.com", role="student", group=platform_perms.GROUP_TEACHER, is_staff=True)
        self.teacher2 = self.make_user("teacher2@example.com", role="student", group=platform_perms.GROUP_TEACHER, is_staff=True)
        self.student = self.make_user("student@example.com", role="student")
        self.student2 = self.make_user("student2@example.com", role="student")
        self.academic_admin = self.make_user(
            "academic@example.com",
            role="admin",
            group=platform_perms.GROUP_ACADEMIC_ADMIN,
            is_staff=True,
        )
        self.course = Course.objects.create(
            title="Teacher Course",
            title_en="Teacher Course",
            slug="teacher-course",
            level=self.level,
            teacher=self.teacher,
            created_by=self.teacher,
            status="draft",
            language="bilingual",
        )
        self.other_course = Course.objects.create(
            title="Other Course",
            slug="other-course",
            level=self.level,
            teacher=self.teacher2,
            created_by=self.teacher2,
            status="draft",
        )
        self.enrollment = CourseEnrollment.objects.create(
            user=self.student,
            course=self.course,
            progress_percentage=45,
        )
        CourseEnrollment.objects.create(
            user=self.student2,
            course=self.other_course,
            progress_percentage=70,
        )
        self.lesson = Lesson.objects.create(
            course=self.course,
            title="Lesson One",
            title_en="Lesson One",
            order=1,
            lesson_type="listening",
            cefr_level="A1",
            skill="listening",
            created_by=self.teacher,
            status="draft",
        )
        CourseLessonProgress.objects.create(
            user=self.student,
            lesson=self.lesson,
            video_completed=True,
            quiz_score=80,
        )
        self.payment = PaymentSubmission.objects.create(
            user=self.student,
            plan="monthly",
            method="bankak",
            amount_sdg=30000,
            screenshot=SimpleUploadedFile("proof.png", b"img", content_type="image/png"),
            status="pending",
        )

    def make_user(self, email, *, role="student", group=None, is_staff=False):
        user = self.User.objects.create_user(username=email, email=email, password="pw", is_staff=is_staff)
        user.profile.role = role
        user.profile.full_name = email.split("@", 1)[0].title()
        user.profile.preferred_language = "en"
        user.profile.onboarding_completed = True
        user.profile.email_verified = True
        user.profile.subscription_status = "active"
        user.profile.save()
        if group:
            user.groups.add(Group.objects.get(name=group))
        return user
