from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


NOTE_VISIBILITY_CHOICES = [
    ("teacher_only", _("Teacher only")),
    ("student_visible", _("Student visible")),
    ("academic_admin_visible", _("Academic admin visible")),
]

ASSIGNMENT_TYPE_CHOICES = [
    ("writing", _("Writing")),
    ("speaking", _("Speaking")),
    ("quiz", _("Quiz")),
    ("reading", _("Reading")),
    ("custom", _("Custom")),
]

SUBMISSION_STATUS_CHOICES = [
    ("submitted", _("Submitted")),
    ("reviewed", _("Reviewed")),
    ("needs_revision", _("Needs revision")),
]


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
        verbose_name=_("User"),
    )
    bio_ar = models.TextField(blank=True, verbose_name=_("Arabic bio"))
    bio_en = models.TextField(blank=True, verbose_name=_("English bio"))
    specialization = models.CharField(max_length=160, blank=True, verbose_name=_("Specialization"))
    avatar = models.ImageField(upload_to="teachers/avatars/%Y/%m/", blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Active"))
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Approved at"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email", "user__username"]
        verbose_name = _("Teacher profile")
        verbose_name_plural = _("Teacher profiles")

    def __str__(self):
        return getattr(self.user, "email", "") or self.user.get_username()


class TeacherStudentNote(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_notes_authored",
        verbose_name=_("Teacher"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_notes_received",
        verbose_name=_("Student"),
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="teacher_student_notes",
        verbose_name=_("Course"),
    )
    note = models.TextField(verbose_name=_("Note"))
    visibility = models.CharField(
        max_length=24,
        choices=NOTE_VISIBILITY_CHOICES,
        default="teacher_only",
        verbose_name=_("Visibility"),
    )
    needs_support = models.BooleanField(default=False, verbose_name=_("Needs support"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["teacher", "-created_at"]),
            models.Index(fields=["student", "course"]),
        ]
        verbose_name = _("Teacher student note")
        verbose_name_plural = _("Teacher student notes")

    def __str__(self):
        return f"Note<{self.teacher_id}->{self.student_id}>"


class TeacherAssignment(models.Model):
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_assignments",
        verbose_name=_("Teacher"),
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="teacher_assignments",
        verbose_name=_("Course"),
    )
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teacher_assignments",
        verbose_name=_("Lesson"),
    )
    title_ar = models.CharField(max_length=200, blank=True, verbose_name=_("Arabic title"))
    title_en = models.CharField(max_length=200, blank=True, verbose_name=_("English title"))
    instructions_ar = models.TextField(blank=True, verbose_name=_("Arabic instructions"))
    instructions_en = models.TextField(blank=True, verbose_name=_("English instructions"))
    assignment_type = models.CharField(
        max_length=16,
        choices=ASSIGNMENT_TYPE_CHOICES,
        default="custom",
        verbose_name=_("Assignment type"),
    )
    due_date = models.DateTimeField(null=True, blank=True, verbose_name=_("Due date"))
    xp_reward = models.PositiveSmallIntegerField(default=0, verbose_name=_("XP reward"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["teacher", "-created_at"]),
            models.Index(fields=["course", "is_active"]),
        ]
        verbose_name = _("Teacher assignment")
        verbose_name_plural = _("Teacher assignments")

    def __str__(self):
        return self.title_en or self.title_ar or f"Assignment {self.pk}"


class StudentAssignmentSubmission(models.Model):
    assignment = models.ForeignKey(
        TeacherAssignment,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name=_("Assignment"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
        verbose_name=_("Student"),
    )
    text_answer = models.TextField(blank=True, verbose_name=_("Text answer"))
    audio_file = models.FileField(upload_to="assignments/audio/%Y/%m/", blank=True, null=True)
    file = models.FileField(upload_to="assignments/files/%Y/%m/", blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name=_("Score"))
    feedback = models.TextField(blank=True, verbose_name=_("Feedback"))
    status = models.CharField(
        max_length=16,
        choices=SUBMISSION_STATUS_CHOICES,
        default="submitted",
        db_index=True,
        verbose_name=_("Status"),
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "student"],
                name="unique_submission_per_assignment_student",
            )
        ]
        indexes = [
            models.Index(fields=["student", "-submitted_at"]),
            models.Index(fields=["assignment", "status"]),
        ]
        verbose_name = _("Student assignment submission")
        verbose_name_plural = _("Student assignment submissions")

    def __str__(self):
        return f"Submission<{self.assignment_id}/{self.student_id}>"
