from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


# Platform's default cut (%). The teacher keeps (100 - this). Overridable
# per teacher via TeacherProfile.commission_rate. The roadmap example uses a
# 70/30 teacher/platform split, i.e. a 30% platform commission.
DEFAULT_PLATFORM_COMMISSION_RATE = 30


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

    # --- Marketplace fields (Prompt 1) ---------------------------------
    # Reference hourly rate the teacher charges (informational; the actual
    # payout is derived from the subscription price via the split below).
    hourly_rate_sdg = models.PositiveIntegerField(
        default=0, verbose_name=_("Hourly rate (SDG)"),
    )
    # The platform's commission percentage (0–100). Teacher keeps the rest.
    commission_rate = models.PositiveIntegerField(
        default=DEFAULT_PLATFORM_COMMISSION_RATE,
        validators=[MaxValueValidator(100)],
        verbose_name=_("Platform commission rate (%)"),
        help_text=_("Percent the platform keeps; the teacher receives the remainder."),
    )
    # Average 0.00–5.00 star rating.
    rating = models.DecimalField(
        max_digits=3, decimal_places=2, default=0,
        validators=[MaxValueValidator(5)],
        verbose_name=_("Rating"),
    )
    is_featured = models.BooleanField(
        default=False, db_index=True, verbose_name=_("Featured"),
    )
    # Comma-separated CEFR levels this teacher focuses on, e.g. "A0,A1,A2".
    # Blank = available for any level.
    cefr_focus = models.CharField(
        max_length=64, blank=True, verbose_name=_("CEFR focus"),
        help_text=_("Comma-separated levels, e.g. A0,A1,A2. Blank = all levels."),
    )

    class Meta:
        ordering = ["user__email", "user__username"]
        verbose_name = _("Teacher profile")
        verbose_name_plural = _("Teacher profiles")

    def __str__(self):
        return getattr(self.user, "email", "") or self.user.get_username()

    # --- Revenue split helpers -----------------------------------------
    def teacher_share(self, amount_sdg: int) -> int:
        """Integer SDG the teacher earns from a subscription of this amount."""
        amount = int(amount_sdg or 0)
        rate = min(int(self.commission_rate or 0), 100)
        return amount * (100 - rate) // 100

    def platform_share(self, amount_sdg: int) -> int:
        """Integer SDG the platform keeps (gets any rounding remainder)."""
        return int(amount_sdg or 0) - self.teacher_share(amount_sdg)

    def teaches_level(self, cefr_level: str | None) -> bool:
        """True if this teacher covers ``cefr_level`` (blank focus = all)."""
        focus = (self.cefr_focus or "").strip()
        if not focus:
            return True
        levels = {p.strip().upper() for p in focus.split(",") if p.strip()}
        return not cefr_level or cefr_level.upper() in levels


class StudentTeacherRelation(models.Model):
    """Links a student to the teacher they chose in the Marketplace.

    A student may have at most one *active* relation at a time; selecting a
    new teacher deactivates the previous one (history is preserved). This is
    additive — it never gates lesson access on its own.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_relations",
        verbose_name=_("Student"),
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_relations",
        verbose_name=_("Teacher"),
    )
    is_active = models.BooleanField(default=True, db_index=True)
    cefr_level_at_selection = models.CharField(max_length=2, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Student–teacher relation")
        verbose_name_plural = _("Student–teacher relations")
        indexes = [
            models.Index(fields=["student", "is_active"]),
        ]
        constraints = [
            # One row per (student, teacher) pair — makes get_or_create race-safe.
            models.UniqueConstraint(fields=["student", "teacher"], name="uniq_student_teacher_relation"),
        ]

    def __str__(self):
        return f"{self.student} → {self.teacher}"

    @classmethod
    def active_for(cls, student):
        """The student's current active teacher relation, or None."""
        return cls.objects.filter(student=student, is_active=True).select_related("teacher").first()

    @classmethod
    def set_active(cls, student, teacher, cefr_level: str = ""):
        """Make ``teacher`` the student's single active choice.

        Deactivates any other active relation first, then reactivates (or
        creates) the row for this teacher. Serialised per-student under a
        transaction + row lock so two concurrent selections can't leave the
        student with two active teachers. Idempotent.
        """
        from django.db import transaction

        with transaction.atomic():
            # Lock the student's existing relation rows (no-op on SQLite) so
            # concurrent set_active calls for the same student serialise.
            list(cls.objects.select_for_update().filter(student=student))
            cls.objects.filter(student=student, is_active=True).exclude(teacher=teacher).update(is_active=False)
            relation, _created = cls.objects.get_or_create(student=student, teacher=teacher)
            relation.is_active = True
            if cefr_level:
                relation.cefr_level_at_selection = cefr_level
            relation.save(update_fields=["is_active", "cefr_level_at_selection", "updated_at"])
        return relation


LIVE_SESSION_STATUS_CHOICES = [
    ("scheduled", _("Scheduled")),
    ("completed", _("Completed")),
    ("cancelled", _("Cancelled")),
]

# Max live sessions a teacher may schedule per course per ISO week.
MAX_LIVE_SESSIONS_PER_WEEK = 2


class LiveSession(models.Model):
    """A scheduled live class (Google Meet) between a teacher and their
    course's students. Capped at two per course per week.
    """

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="live_sessions",
        verbose_name=_("Teacher"),
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="live_sessions",
        verbose_name=_("Course"),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    scheduled_at = models.DateTimeField(verbose_name=_("Scheduled at"))
    duration_minutes = models.PositiveIntegerField(default=60, verbose_name=_("Duration (minutes)"))
    meet_link = models.URLField(blank=True, verbose_name=_("Google Meet link"))
    status = models.CharField(
        max_length=10, choices=LIVE_SESSION_STATUS_CHOICES, default="scheduled",
        db_index=True, verbose_name=_("Status"),
    )
    # Set when the 30-minute reminder has gone out, so it fires only once.
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-scheduled_at"]
        verbose_name = _("Live session")
        verbose_name_plural = _("Live sessions")
        indexes = [
            models.Index(fields=["teacher", "scheduled_at"]),
            models.Index(fields=["status", "scheduled_at"]),
        ]

    def __str__(self):
        return f"{self.title} — {self.scheduled_at:%Y-%m-%d %H:%M}"

    @property
    def ends_at(self):
        return self.scheduled_at + timedelta(minutes=self.duration_minutes or 0)

    @staticmethod
    def _week_bounds(when):
        """Monday 00:00 .. next Monday 00:00 around ``when``."""
        start = (when - timedelta(days=when.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        return start, start + timedelta(days=7)

    @classmethod
    def weekly_count(cls, teacher, course, when, exclude_pk=None):
        """Active (non-cancelled) sessions for this teacher+course in the
        ISO week containing ``when``."""
        start, end = cls._week_bounds(when)
        qs = (
            cls.objects.filter(teacher=teacher, course=course, scheduled_at__gte=start, scheduled_at__lt=end)
            .exclude(status="cancelled")
        )
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        return qs.count()


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
