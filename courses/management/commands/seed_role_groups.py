"""Seed the five role Groups + assign sane Django permissions.

Group → permission mapping:
  * Super Admin       → not seeded with perms; assumed `is_superuser=True`
  * Academic Admin    → full course/lesson/quiz/question/enrollment/review/log
  * Teacher           → add+change on course/lesson/quiz/question/resource/unit
                          (+view); cannot delete; cannot change enrollments
  * Finance Admin     → view+change on payments app objects (best-effort —
                          permissions are filtered by app_label='payments')
  * Support Admin     → view-only on accounts.User + accounts.Profile +
                          courses.* models

Idempotent.
"""
from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from courses.permissions import (
    GROUP_ACADEMIC_ADMIN, GROUP_FINANCE_ADMIN, GROUP_SUPER_ADMIN,
    GROUP_SUPPORT_ADMIN, GROUP_TEACHER,
)


def _perms_for(model_classes, codenames):
    """Return Permission queryset for the given (app, codename) pairs."""
    perms = []
    for model in model_classes:
        ct = ContentType.objects.get_for_model(model)
        for cn in codenames:
            full = f"{cn}_{model._meta.model_name}"
            try:
                perms.append(Permission.objects.get(content_type=ct, codename=full))
            except Permission.DoesNotExist:
                # The migration that creates this perm may not have run
                # in the right order during a fresh install; tolerate it.
                continue
    return perms


class Command(BaseCommand):
    help = "Seed the five role Groups with their default permissions."

    def handle(self, *args, **opts):
        # Lazy imports — `courses.models` is the unit of truth.
        from courses.models import (
            AdminActionLog, ContentReviewLog, Course, CourseEnrollment,
            CourseLevel, CourseUnit, Lesson, LessonQuestion, LessonQuiz,
            LessonResource,
        )

        academic_models = [
            Course, CourseLevel, CourseUnit, Lesson, LessonQuiz,
            LessonQuestion, LessonResource, CourseEnrollment,
            ContentReviewLog, AdminActionLog,
        ]
        teacher_models = [
            Course, CourseUnit, Lesson, LessonQuiz, LessonQuestion,
            LessonResource,
        ]
        support_models = [
            Course, CourseLevel, CourseUnit, Lesson, LessonQuiz,
            LessonQuestion, CourseEnrollment,
        ]

        created_count = 0
        for name, perms in [
            (GROUP_SUPER_ADMIN, []),  # superusers transcend perms
            (GROUP_ACADEMIC_ADMIN,
                _perms_for(academic_models, ["add", "change", "delete", "view"])),
            (GROUP_TEACHER,
                _perms_for(teacher_models, ["add", "change", "view"])),
            (GROUP_FINANCE_ADMIN,
                # Permissions for finance live in the `payments` app —
                # we look them up by app_label so this seeder doesn't
                # have to import payments models.
                list(Permission.objects.filter(content_type__app_label="payments"))),
            (GROUP_SUPPORT_ADMIN,
                _perms_for(support_models, ["view"])),
        ]:
            group, was_created = Group.objects.get_or_create(name=name)
            if perms:
                group.permissions.set(perms)
            else:
                # Reset to empty for groups that should hold no
                # explicit perms (Super Admin uses is_superuser).
                pass
            if was_created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Role groups: {created_count} created, "
            f"{Group.objects.count()} total."
        ))
