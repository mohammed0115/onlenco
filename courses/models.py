"""Course-management models for the Onlenco LMS.

Architectural choices
---------------------
* `CourseLevel` is its own table (rather than a CharField CEFR enum) so
  admins can reorder/deactivate levels through the admin UI.
* `Course` carries a `status` workflow (draft → pending_review →
  published → archived) that's enforced by the admin's `submit_for_review`
  / `approve` / `publish` actions.
* `Lesson` is *new* (parallel to the legacy `lessons.Lesson`). The
  legacy model is keyed off a single video URL; this one supports a
  full set of media (file uploads + transcripts + content blocks). A
  data migration from the legacy model is deliberately out of scope —
  the two coexist for now.
* `created_by` on Course/Lesson is the source of truth for "is this
  teacher allowed to edit it?" — see `courses.permissions`.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import CEFR_CHOICES

from .validators import (
    parse_video_url, validate_audio, validate_document, validate_image,
    validate_resource_file, validate_video, validate_video_url,
)


# ---------------------------------------------------------------------------
# Status / type enums
# ---------------------------------------------------------------------------

COURSE_STATUS_CHOICES = [
    ("draft",          _("Draft")),
    ("pending_review", _("Pending review")),
    ("published",      _("Published")),
    ("rejected",       _("Rejected")),
    ("archived",       _("Archived")),
]
LESSON_STATUS_CHOICES = [
    ("draft",          _("Draft")),
    ("pending_review", _("Pending review")),
    ("published",      _("Published")),
    ("rejected",       _("Rejected")),
]
COURSE_LANGUAGE_CHOICES = [
    ("ar",        _("Arabic")),
    ("en",        _("English")),
    ("bilingual", _("Bilingual")),
]
LESSON_TYPE_CHOICES = [
    ("reading",    _("Reading")),
    ("writing",    _("Writing")),
    ("listening",  _("Listening")),
    ("speaking",   _("Speaking")),
    ("grammar",    _("Grammar")),
    ("vocabulary", _("Vocabulary")),
    ("mixed",      _("Mixed")),
]
SKILL_CHOICES = LESSON_TYPE_CHOICES   # alias — same set, different semantics
RESOURCE_TYPE_CHOICES = [
    ("pdf",       _("PDF")),
    ("video",     _("Video")),
    ("audio",     _("Audio")),
    ("image",     _("Image")),
    ("link",      _("External link")),
    ("worksheet", _("Worksheet")),
]
QUESTION_TYPE_CHOICES = [
    ("multiple_choice",   _("Multiple choice")),
    ("fill_blank",        _("Fill in the blank")),
    ("correction",        _("Correction")),
    ("sentence_ordering", _("Sentence ordering")),
    ("translation",       _("Translation")),
    ("short_answer",      _("Short answer")),
    ("speaking_prompt",   _("Speaking prompt")),
    ("writing_prompt",    _("Writing prompt")),
]
ENROLLMENT_STATUS_CHOICES = [
    ("active",    _("Active")),
    ("completed", _("Completed")),
    ("paused",    _("Paused")),
]
REVIEW_STATUS_CHOICES = [
    ("pending",   _("Pending")),
    ("approved",  _("Approved")),
    ("rejected",  _("Rejected")),
]


# ---------------------------------------------------------------------------
# 1. CourseLevel
# ---------------------------------------------------------------------------

class CourseLevel(models.Model):
    """CEFR level (A0…C2) as a first-class table. Lets admins reorder
    or deactivate levels without a code change."""

    code = models.CharField(
        max_length=2, choices=CEFR_CHOICES, unique=True,
        verbose_name=_("CEFR code"),
    )
    name = models.CharField(max_length=80, verbose_name=_("Name"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Display order"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        ordering = ["order", "code"]
        verbose_name = _("Course level")
        verbose_name_plural = _("Course levels")

    def __str__(self):
        return f"{self.code} — {self.name}"


# ---------------------------------------------------------------------------
# 2. Course
# ---------------------------------------------------------------------------

class Course(models.Model):
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    title_ar = models.CharField(
        max_length=200, blank=True, verbose_name=_("Arabic title"),
    )
    title_en = models.CharField(
        max_length=200, blank=True, verbose_name=_("English title"),
    )
    slug = models.SlugField(max_length=220, unique=True, verbose_name=_("Slug"))
    # Stable, human-readable identifier auto-generated on first save —
    # e.g. ``ONL-A1-COURSE-001``. Used for admin search, exports, and
    # cross-app references. Never changes after creation (unlike slug
    # or title which may be edited).
    code = models.CharField(
        max_length=50, unique=True, blank=True, db_index=True,
        verbose_name=_("Auto code"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    description_ar = models.TextField(blank=True, verbose_name=_("Arabic description"))
    description_en = models.TextField(blank=True, verbose_name=_("English description"))
    level = models.ForeignKey(
        CourseLevel, on_delete=models.PROTECT, related_name="courses",
        verbose_name=_("Level"),
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="taught_courses",
        verbose_name=_("Teacher"),
    )
    language = models.CharField(
        max_length=10, choices=COURSE_LANGUAGE_CHOICES, default="bilingual",
        verbose_name=_("Language"),
    )
    status = models.CharField(
        max_length=16, choices=COURSE_STATUS_CHOICES, default="draft",
        verbose_name=_("Status"),
    )
    cover_image = models.ImageField(
        upload_to="courses/covers/%Y/%m/", blank=True, null=True,
        validators=[validate_image], verbose_name=_("Cover image"),
    )
    intro_video = models.FileField(
        upload_to="courses/intros/%Y/%m/", blank=True, null=True,
        validators=[validate_video], verbose_name=_("Intro video"),
    )
    estimated_duration_hours = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Estimated duration (hours)"),
    )
    learning_objectives = models.TextField(
        blank=True, verbose_name=_("Learning objectives"),
    )
    objectives_ar = models.TextField(blank=True, verbose_name=_("Arabic objectives"))
    objectives_en = models.TextField(blank=True, verbose_name=_("English objectives"))
    prerequisites = models.TextField(blank=True, verbose_name=_("Prerequisites"))
    is_free = models.BooleanField(default=False, verbose_name=_("Free"))
    drip_enabled = models.BooleanField(
        default=True, verbose_name=_("Daily lesson unlock"),
        help_text=_(
            "Release one lesson per day: the next lesson unlocks only "
            "after the previous one is completed and a calendar day has "
            "passed. Turn off to open every lesson at once."
        ),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_courses",
        verbose_name=_("Created by"),
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_courses",
        verbose_name=_("Reviewed by"),
    )
    reviewed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Reviewed at"),
    )
    review_notes = models.TextField(
        blank=True, verbose_name=_("Review notes"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["level", "status"]),
            models.Index(fields=["teacher", "-created_at"]),
        ]
        verbose_name = _("Course")
        verbose_name_plural = _("Courses")

    def save(self, *args, **kwargs):
        # Auto-assign code on first save. Never re-generate, so the
        # identifier stays stable even if level / title change.
        if not self.code and self.level_id:
            from courses.services.code_generator import (
                generate_course_code, next_course_sequence,
            )
            existing = (
                Course.objects.filter(level=self.level)
                .exclude(pk=self.pk)
                .values_list("code", flat=True)
            )
            seq = next_course_sequence(existing)
            self.code = generate_course_code(self.level.code, seq)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# 3. CourseUnit
# ---------------------------------------------------------------------------

class CourseUnit(models.Model):
    """Bundle of lessons inside a course.

    Spec rule: a Unit carries **up to 3 Lessons**, and can only be
    *published* when all 3 are active. The cap is enforced at the
    application layer via ``Lesson.clean()`` — easy to override for
    legacy data, and easy to relax later if pedagogy changes.
    """

    MAX_LESSONS_PER_UNIT = 3

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="units",
        verbose_name=_("Course"),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    title_ar = models.CharField(max_length=200, blank=True, verbose_name=_("Arabic title"))
    title_en = models.CharField(max_length=200, blank=True, verbose_name=_("English title"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    description_ar = models.TextField(blank=True, verbose_name=_("Arabic description"))
    description_en = models.TextField(blank=True, verbose_name=_("English description"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Order"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Active"))
    is_published = models.BooleanField(default=False, db_index=True, verbose_name=_("Published"))
    code = models.CharField(
        max_length=50, unique=True, blank=True, db_index=True,
        verbose_name=_("Auto code"),
    )

    class Meta:
        ordering = ["course", "order", "id"]
        verbose_name = _("Course unit")
        verbose_name_plural = _("Course units")

    def __str__(self):
        return f"{self.course.title} — {self.title}"

    def save(self, *args, **kwargs):
        if not self.code and self.course_id:
            from courses.services.code_generator import (
                generate_unit_code, parse_course_sequence,
            )
            course_seq = parse_course_sequence(self.course.code)
            self.code = generate_unit_code(
                self.course.level.code, course_seq, self.order,
            )
        super().save(*args, **kwargs)

    @property
    def lesson_count(self) -> int:
        return self.lessons.count()

    @property
    def is_complete(self) -> bool:
        """True when the unit has its full set of 3 active lessons."""
        return self.lessons.filter(is_active=True).count() >= self.MAX_LESSONS_PER_UNIT

    def can_be_published(self) -> bool:
        return self.is_complete

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.is_published and not self.is_complete:
            raise ValidationError(
                {"is_published": _(
                    "A Unit can only be published once it has %(n)s active lessons."
                ) % {"n": self.MAX_LESSONS_PER_UNIT}},
            )


# ---------------------------------------------------------------------------
# 4. Lesson
# ---------------------------------------------------------------------------

class Lesson(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="lessons",
        verbose_name=_("Course"),
    )
    unit = models.ForeignKey(
        CourseUnit, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="lessons", verbose_name=_("Unit"),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    title_ar = models.CharField(
        max_length=200, blank=True, verbose_name=_("Arabic title"),
    )
    title_en = models.CharField(
        max_length=200, blank=True, verbose_name=_("English title"),
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Order"))
    lesson_type = models.CharField(
        max_length=16, choices=LESSON_TYPE_CHOICES, default="mixed",
        verbose_name=_("Lesson type"),
    )
    cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True,
        verbose_name=_("CEFR level"),
    )
    skill = models.CharField(
        max_length=16, choices=SKILL_CHOICES, blank=True,
        verbose_name=_("Skill"),
    )
    grammar_topic = models.CharField(
        max_length=120, blank=True, verbose_name=_("Grammar topic"),
    )
    vocabulary_topic = models.CharField(
        max_length=120, blank=True, verbose_name=_("Vocabulary topic"),
    )
    video_file = models.FileField(
        upload_to="lessons/video/%Y/%m/", blank=True, null=True,
        validators=[validate_video], verbose_name=_("Video file"),
        help_text=_("Upload a .mp4, .webm or .m4v file. Played first if both this and the URL are set."),
    )
    video_url = models.URLField(
        blank=True, verbose_name=_("Video URL"),
        help_text=_("YouTube, Vimeo, or a direct .mp4/.webm link. Used when no file is uploaded or the file is missing."),
    )
    audio_file = models.FileField(
        upload_to="lessons/audio/%Y/%m/", blank=True, null=True,
        validators=[validate_audio], verbose_name=_("Audio file"),
    )
    pdf_file = models.FileField(
        upload_to="lessons/pdf/%Y/%m/", blank=True, null=True,
        validators=[validate_document], verbose_name=_("PDF file"),
    )
    content_html = models.TextField(blank=True, verbose_name=_("Content"))
    content_ar = models.TextField(blank=True, verbose_name=_("Arabic content"))
    content_en = models.TextField(blank=True, verbose_name=_("English content"))
    code = models.CharField(
        max_length=50, unique=True, blank=True, db_index=True,
        verbose_name=_("Auto code"),
    )
    transcript = models.TextField(blank=True, verbose_name=_("Transcript"))
    duration_minutes = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Duration (minutes)"),
    )
    status = models.CharField(
        max_length=16, choices=LESSON_STATUS_CHOICES, default="draft",
        verbose_name=_("Status"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_lessons",
        verbose_name=_("Created by"),
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_lessons",
        verbose_name=_("Reviewed by"),
    )
    reviewed_at = models.DateTimeField(
        null=True, blank=True, verbose_name=_("Reviewed at"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course", "order", "id"]
        indexes = [
            models.Index(fields=["course", "order"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]
        verbose_name = _("Lesson")
        verbose_name_plural = _("Lessons")

    def __str__(self):
        return f"{self.course.title} — {self.title}"

    def save(self, *args, **kwargs):
        if not self.code and self.course_id:
            from courses.services.code_generator import (
                fallback_lesson_code, generate_lesson_code,
                parse_course_sequence,
            )
            level_code = self.course.level.code if self.course.level_id else ""
            if self.unit_id and self.unit and self.course.code:
                course_seq = parse_course_sequence(self.course.code)
                self.code = generate_lesson_code(
                    level_code, course_seq, self.unit.order, self.order,
                )
            elif self.pk:
                # Standalone lesson (no unit yet) — pk-anchored fallback
                # keeps the unique constraint satisfied. Re-saving after
                # a unit is attached does NOT re-generate.
                self.code = fallback_lesson_code(self.pk, level_code)
        super().save(*args, **kwargs)
        # If the code couldn't be set BEFORE save (no pk yet, no unit),
        # set it now and save once more.
        if not self.code:
            from courses.services.code_generator import fallback_lesson_code
            level_code = self.course.level.code if self.course.level_id else ""
            self.code = fallback_lesson_code(self.pk, level_code)
            super().save(update_fields=["code"])

    def clean(self):
        super().clean()
        if self.video_url:
            validate_video_url(self.video_url)
        # Spec: a Unit carries at most 3 Lessons. Enforced on the
        # lesson side because that's where the constraint can be
        # checked at save-time (clean() on Unit would only fire when
        # the Unit itself is saved, not when a lesson is attached).
        if self.unit_id:
            from django.core.exceptions import ValidationError
            sibling_count = (
                Lesson.objects
                .filter(unit_id=self.unit_id)
                .exclude(pk=self.pk)
                .count()
            )
            if sibling_count >= CourseUnit.MAX_LESSONS_PER_UNIT:
                raise ValidationError(
                    {"unit": _(
                        "This unit already has %(n)s lessons — the maximum allowed."
                    ) % {"n": CourseUnit.MAX_LESSONS_PER_UNIT}},
                )

    def get_video_embed(self) -> dict | None:
        """Resolve which video to play.

        Order: uploaded file first; fall back to the URL when the file is
        missing or unreadable. Returned dict carries enough info for a
        template to pick the right player:
            {"kind": "file"|"youtube"|"vimeo"|"direct",
             "url":  <playable URL or media URL>,
             "embed_url": <iframe src — youtube/vimeo only>}
        Returns None when neither source is set.
        """
        # Upload wins. We probe `.url` lazily because `FileField.url` raises
        # on storages that haven't been configured (e.g. unit tests).
        if self.video_file:
            try:
                return {"kind": "file", "url": self.video_file.url, "embed_url": None}
            except Exception:
                pass
        parsed = parse_video_url(self.video_url) if self.video_url else None
        if parsed:
            return {"kind": parsed["kind"], "url": self.video_url,
                    "embed_url": parsed.get("embed_url")}
        return None


# ---------------------------------------------------------------------------
# 5. LessonResource
# ---------------------------------------------------------------------------

class LessonResource(models.Model):
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="resources",
        verbose_name=_("Lesson"),
    )
    resource_type = models.CharField(
        max_length=12, choices=RESOURCE_TYPE_CHOICES,
        verbose_name=_("Resource type"),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    file = models.FileField(
        upload_to="lessons/resources/%Y/%m/", blank=True, null=True,
        verbose_name=_("File"),
    )
    url = models.URLField(blank=True, verbose_name=_("URL"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        ordering = ["lesson", "order", "id"]
        verbose_name = _("Lesson resource")
        verbose_name_plural = _("Lesson resources")

    def __str__(self):
        return f"{self.lesson.title} — {self.title}"

    def clean(self):
        super().clean()
        if self.file:
            validate_resource_file(self.file, self.resource_type)


# ---------------------------------------------------------------------------
# 6. LessonQuiz
# ---------------------------------------------------------------------------

class LessonQuiz(models.Model):
    lesson = models.OneToOneField(
        Lesson, on_delete=models.CASCADE, related_name="quiz",
        verbose_name=_("Lesson"),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    title_ar = models.CharField(
        max_length=200, blank=True, verbose_name=_("Arabic title"),
    )
    title_en = models.CharField(
        max_length=200, blank=True, verbose_name=_("English title"),
    )
    passing_score = models.PositiveSmallIntegerField(
        default=70, verbose_name=_("Passing score (%)"),
    )
    time_limit_minutes = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Time limit (minutes)"),
        help_text=_("0 = no limit"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))
    code = models.CharField(
        max_length=60, unique=True, blank=True, db_index=True,
        verbose_name=_("Auto code"),
    )

    class Meta:
        verbose_name = _("Lesson quiz")
        verbose_name_plural = _("Lesson quizzes")

    def __str__(self):
        return f"Quiz: {self.lesson.title}"

    def save(self, *args, **kwargs):
        if not self.code and self.lesson_id and self.lesson.code:
            from courses.services.code_generator import generate_quiz_code
            self.code = generate_quiz_code(self.lesson.code)
        super().save(*args, **kwargs)
        # Quiz created before the lesson got its code? Re-anchor once
        # the lesson code is available.
        if not self.code and self.lesson_id and self.lesson.code:
            from courses.services.code_generator import generate_quiz_code
            self.code = generate_quiz_code(self.lesson.code)
            super().save(update_fields=["code"])
        elif not self.code and self.pk:
            from courses.services.code_generator import fallback_quiz_code
            self.code = fallback_quiz_code(self.pk)
            super().save(update_fields=["code"])


# ---------------------------------------------------------------------------
# 7. LessonQuestion
# ---------------------------------------------------------------------------

class LessonQuestion(models.Model):
    quiz = models.ForeignKey(
        LessonQuiz, on_delete=models.CASCADE, related_name="questions",
        verbose_name=_("Quiz"),
    )
    question_type = models.CharField(
        max_length=20, choices=QUESTION_TYPE_CHOICES,
        verbose_name=_("Question type"),
    )
    question_text = models.TextField(verbose_name=_("Question text"))
    question_text_ar = models.TextField(blank=True, verbose_name=_("Arabic question text"))
    question_text_en = models.TextField(blank=True, verbose_name=_("English question text"))
    options = models.JSONField(
        default=list, blank=True, verbose_name=_("Options"),
    )
    correct_answer = models.TextField(
        blank=True, verbose_name=_("Correct answer"),
    )
    explanation = models.TextField(blank=True, verbose_name=_("Explanation"))
    explanation_ar = models.TextField(blank=True, verbose_name=_("Arabic explanation"))
    explanation_en = models.TextField(blank=True, verbose_name=_("English explanation"))
    difficulty_score = models.FloatField(
        default=0.5, verbose_name=_("Difficulty (0..1)"),
    )
    points = models.PositiveSmallIntegerField(
        default=1, verbose_name=_("Points"),
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Order"))

    class Meta:
        ordering = ["quiz", "order", "id"]
        verbose_name = _("Lesson question")
        verbose_name_plural = _("Lesson questions")

    def __str__(self):
        return f"{self.quiz.title} — Q{self.order}"

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if not (self.question_text or self.question_text_ar or self.question_text_en):
            raise ValidationError(_("Question text is required."))
        if not self.correct_answer:
            raise ValidationError(_("Correct answer is required."))
        if self.question_type == "multiple_choice":
            opts = list(self.options or [])
            if len(opts) < 2:
                raise ValidationError(
                    _("Multiple-choice questions need at least 2 options.")
                )
            if self.correct_answer not in opts:
                raise ValidationError(
                    _("The correct answer must appear in the options list.")
                )


# ---------------------------------------------------------------------------
# 8. CourseEnrollment
# ---------------------------------------------------------------------------

class CourseEnrollment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="course_enrollments", verbose_name=_("Student"),
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE,
        related_name="enrollments", verbose_name=_("Course"),
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=12, choices=ENROLLMENT_STATUS_CHOICES, default="active",
        verbose_name=_("Status"),
    )
    progress_percentage = models.FloatField(
        default=0.0, verbose_name=_("Progress %"),
    )

    class Meta:
        ordering = ["-enrolled_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "course"],
                name="course_enrollment_unique_user_course",
            ),
        ]
        indexes = [
            models.Index(fields=["course", "status"]),
        ]
        verbose_name = _("Course enrollment")
        verbose_name_plural = _("Course enrollments")

    def __str__(self):
        return f"{self.user_id} → {self.course_id}"


# ---------------------------------------------------------------------------
# 9. ContentReviewLog
# ---------------------------------------------------------------------------

class ContentReviewLog(models.Model):
    """One review event per (object, submitter, reviewer). Generic FK
    so the same log captures Course AND Lesson reviews."""

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        verbose_name=_("Content type"),
    )
    object_id = models.PositiveIntegerField(verbose_name=_("Object ID"))
    content_object = GenericForeignKey("content_type", "object_id")

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="content_submissions",
        verbose_name=_("Submitted by"),
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="content_reviews",
        verbose_name=_("Reviewed by"),
    )
    status = models.CharField(
        max_length=10, choices=REVIEW_STATUS_CHOICES, default="pending",
        verbose_name=_("Status"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Notes"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["submitted_by", "-created_at"]),
        ]
        verbose_name = _("Content review log")
        verbose_name_plural = _("Content review logs")

    def __str__(self):
        return f"Review<{self.id}> {self.status}"


# ---------------------------------------------------------------------------
# 10. AdminActionLog
# ---------------------------------------------------------------------------

class AdminActionLog(models.Model):
    """Audit trail for sensitive admin actions (publish, archive,
    teacher reassignment, etc.)."""

    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="admin_actions",
        verbose_name=_("Admin"),
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="admin_actions_targeting",
        verbose_name=_("Target user"),
    )
    action_type = models.CharField(
        max_length=40, verbose_name=_("Action type"),
        help_text=_("e.g. course.publish, lesson.approve"),
    )
    description = models.TextField(blank=True, verbose_name=_("Description"))
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["admin_user", "-created_at"]),
            models.Index(fields=["action_type", "-created_at"]),
        ]
        verbose_name = _("Admin action log")
        verbose_name_plural = _("Admin action logs")

    def __str__(self):
        return f"{self.action_type} @ {self.created_at:%Y-%m-%d}"


# ---------------------------------------------------------------------------
# 11. CourseLessonProgress
# ---------------------------------------------------------------------------

class CourseLessonProgress(models.Model):
    """Per-(user, lesson) progress for the courses-app Lesson.

    Separate from `lessons.LessonProgress` (which tracks the legacy
    `lessons.Lesson`). The activity collector reads from both.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="course_lesson_progress",
    )
    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE,
        related_name="student_progress",
    )
    video_completed = models.BooleanField(default=False)
    quiz_score = models.PositiveSmallIntegerField(null=True, blank=True)
    quiz_passed = models.BooleanField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "lesson"],
                name="courselessonprogress_unique_user_lesson",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-completed_at"]),
            models.Index(fields=["lesson"]),
        ]
        verbose_name = _("Course lesson progress")
        verbose_name_plural = _("Course lesson progress")

    def __str__(self):
        return f"CLP<{self.user_id}> lesson={self.lesson_id} done={bool(self.completed_at)}"

    @property
    def is_complete(self) -> bool:
        if not self.video_completed:
            return False
        if not getattr(self.lesson, "quiz", None):
            return True
        return bool(self.quiz_passed)


# ---------------------------------------------------------------------------
# 12. LessonMedia, QuestionMedia, LessonChecklist, LessonAudioScript,
#     LessonImagePrompt — additive multi-media surface for the Beginner
#     pack (Prompt 02). Every field is optional so existing lessons keep
#     rendering unchanged when no rows exist; a lesson page must work
#     whether or not these tables hold data for it.
# ---------------------------------------------------------------------------

LESSON_MEDIA_TYPE_CHOICES = [
    ("image",    _("Image")),
    ("audio",    _("Audio")),
    ("video",    _("Video")),
    ("document", _("Document")),
]

LESSON_MEDIA_LANGUAGE_CHOICES = [
    ("",   _("Universal / language-neutral")),
    ("en", _("English")),
    ("ar", _("Arabic")),
]


class LessonMedia(models.Model):
    """Additional media attached to a Lesson — more than one image / audio /
    video / pdf per lesson, each with its own caption and language tag.

    The legacy single-FK media fields on `Lesson` (`video_file`, `audio_file`,
    `pdf_file`) are kept as-is for the "one canonical media per lesson"
    case. `LessonMedia` is the multi-row extension used by the Beginner
    pack — e.g. five vocabulary tile images per lesson, each linked to its
    own pronunciation clip.
    """

    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="media",
        verbose_name=_("Lesson"),
    )
    media_type = models.CharField(
        max_length=10, choices=LESSON_MEDIA_TYPE_CHOICES, db_index=True,
        verbose_name=_("Media type"),
    )
    title = models.CharField(
        max_length=200, blank=True, verbose_name=_("Title (English)"),
    )
    title_ar = models.CharField(
        max_length=200, blank=True, verbose_name=_("Title (Arabic)"),
    )
    file = models.FileField(
        upload_to="lessons/media/%Y/%m/", blank=True, null=True,
        verbose_name=_("File"),
        help_text=_("Optional. An empty row is treated as a placeholder."),
    )
    external_url = models.URLField(
        blank=True, max_length=500, verbose_name=_("External URL"),
    )
    language = models.CharField(
        max_length=2, choices=LESSON_MEDIA_LANGUAGE_CHOICES,
        blank=True, default="", verbose_name=_("Language"),
    )
    alt_text = models.CharField(
        max_length=300, blank=True, verbose_name=_("Alt text"),
    )
    transcript = models.TextField(
        blank=True, verbose_name=_("Transcript"),
    )
    duration_seconds = models.PositiveIntegerField(
        default=0, verbose_name=_("Duration (seconds)"),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Sort order"),
    )
    is_active = models.BooleanField(
        default=True, verbose_name=_("Active"),
    )
    generated_by_ai = models.BooleanField(
        default=False, verbose_name=_("Generated by AI"),
    )
    generation_prompt = models.TextField(
        blank=True, verbose_name=_("Generation prompt"),
        help_text=_("Prompt text used when AI-generated. Empty for uploads."),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["lesson", "sort_order", "id"]
        indexes = [
            models.Index(fields=["lesson", "media_type"]),
            models.Index(fields=["lesson", "sort_order"]),
            models.Index(fields=["is_active"]),
        ]
        verbose_name = _("Lesson media")
        verbose_name_plural = _("Lesson media")

    def __str__(self):
        label = self.title or self.alt_text or f"{self.media_type}#{self.pk}"
        return f"{self.lesson_id} · {label}"


QUESTION_MEDIA_TYPE_CHOICES = [
    ("image", _("Image")),
    ("audio", _("Audio")),
    ("video", _("Video")),
]


class QuestionMedia(models.Model):
    """Optional media attached to a `LessonQuestion` — image cue for a
    vocab match, audio prompt for a listening question, etc."""

    question = models.ForeignKey(
        LessonQuestion, on_delete=models.CASCADE, related_name="media",
        verbose_name=_("Question"),
    )
    media_type = models.CharField(
        max_length=10, choices=QUESTION_MEDIA_TYPE_CHOICES, db_index=True,
        verbose_name=_("Media type"),
    )
    file = models.FileField(
        upload_to="lessons/questions/%Y/%m/", blank=True, null=True,
        verbose_name=_("File"),
    )
    external_url = models.URLField(
        blank=True, max_length=500, verbose_name=_("External URL"),
    )
    alt_text = models.CharField(
        max_length=300, blank=True, verbose_name=_("Alt text"),
    )
    transcript = models.TextField(
        blank=True, verbose_name=_("Transcript"),
    )
    language = models.CharField(
        max_length=2, choices=LESSON_MEDIA_LANGUAGE_CHOICES,
        blank=True, default="", verbose_name=_("Language"),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Sort order"),
    )
    is_active = models.BooleanField(
        default=True, verbose_name=_("Active"),
    )
    generation_prompt = models.TextField(
        blank=True, verbose_name=_("Generation prompt"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question", "sort_order", "id"]
        indexes = [
            models.Index(fields=["question", "media_type"]),
        ]
        verbose_name = _("Question media")
        verbose_name_plural = _("Question media")

    def __str__(self):
        return f"Q{self.question_id} · {self.media_type}#{self.pk}"


class LessonChecklist(models.Model):
    """Bilingual checklist items shown at the end of a Lesson. Renders the
    "can-do" statements students tick off (e.g. "I can introduce myself"
    / "أستطيع التعريف بنفسي")."""

    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="checklist_items",
        verbose_name=_("Lesson"),
    )
    text_en = models.CharField(
        max_length=300, verbose_name=_("Text (English)"),
    )
    text_ar = models.CharField(
        max_length=300, blank=True, verbose_name=_("Text (Arabic)"),
        help_text=_("Optional — falls back to English if blank."),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Sort order"),
    )
    is_active = models.BooleanField(
        default=True, verbose_name=_("Active"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lesson", "sort_order", "id"]
        indexes = [
            models.Index(fields=["lesson", "sort_order"]),
        ]
        verbose_name = _("Lesson checklist item")
        verbose_name_plural = _("Lesson checklist items")

    def __str__(self):
        return f"{self.lesson_id} · {self.text_en[:40]}"

    def text_for(self, language: str) -> str:
        """Localised getter — Arabic when requested and present, else English."""
        if (language or "").lower().startswith("ar") and self.text_ar.strip():
            return self.text_ar
        return self.text_en


LESSON_AUDIO_SCRIPT_TYPE_CHOICES = [
    ("intro",      _("Intro")),
    ("vocabulary", _("Vocabulary")),
    ("examples",   _("Examples")),
    ("dialogue",   _("Dialogue")),
    ("listening",  _("Listening")),
    ("quiz",       _("Quiz")),
    ("speaking",   _("Speaking")),
]

LESSON_AUDIO_VOICE_STYLE_CHOICES = [
    ("friendly_teacher", _("Friendly teacher")),
    ("slow_beginner",    _("Slow beginner")),
    ("dialogue",         _("Dialogue (two voices)")),
]


class LessonAudioScript(models.Model):
    """TTS source script for a Lesson. One row per script_type — feeds the
    batch audio generator (Prompt 08). Holds both the raw text and the
    eventually-generated audio file so re-runs are idempotent."""

    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="audio_scripts",
        verbose_name=_("Lesson"),
    )
    script_type = models.CharField(
        max_length=20, choices=LESSON_AUDIO_SCRIPT_TYPE_CHOICES,
        db_index=True, verbose_name=_("Script type"),
    )
    script_text = models.TextField(
        verbose_name=_("Script text"),
        help_text=_("The English copy to be spoken. Use SSML where helpful."),
    )
    voice_style = models.CharField(
        max_length=20, choices=LESSON_AUDIO_VOICE_STYLE_CHOICES,
        default="friendly_teacher", verbose_name=_("Voice style"),
    )
    accent = models.CharField(
        max_length=20, default="american", verbose_name=_("Accent"),
        help_text=_("General American by default. Other values reserved for future."),
    )
    generated_audio = models.FileField(
        upload_to="lessons/audio_scripts/%Y/%m/", blank=True, null=True,
        validators=[validate_audio], verbose_name=_("Generated audio"),
    )
    is_generated = models.BooleanField(
        default=False, verbose_name=_("Generated"),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Sort order"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["lesson", "sort_order", "id"]
        indexes = [
            models.Index(fields=["lesson", "script_type"]),
            models.Index(fields=["is_generated"]),
        ]
        verbose_name = _("Lesson audio script")
        verbose_name_plural = _("Lesson audio scripts")

    def __str__(self):
        return f"{self.lesson_id} · {self.script_type}#{self.pk}"


LESSON_IMAGE_PROMPT_TYPE_CHOICES = [
    ("cover",      _("Cover")),
    ("vocabulary", _("Vocabulary")),
    ("grammar",    _("Grammar")),
    ("quiz",       _("Quiz")),
]


class LessonImagePrompt(models.Model):
    """Image-generation prompt for a Lesson. One row per prompt_type — feeds
    the batch image generator (Prompt 07). Stores both the text prompt and
    the eventually-generated image so re-runs are idempotent."""

    lesson = models.ForeignKey(
        Lesson, on_delete=models.CASCADE, related_name="image_prompts",
        verbose_name=_("Lesson"),
    )
    prompt_type = models.CharField(
        max_length=20, choices=LESSON_IMAGE_PROMPT_TYPE_CHOICES,
        db_index=True, verbose_name=_("Prompt type"),
    )
    prompt = models.TextField(
        verbose_name=_("Prompt"),
        help_text=_("Free-text image generation prompt — keep style guide rules in mind."),
    )
    generated_image = models.ImageField(
        upload_to="lessons/image_prompts/%Y/%m/", blank=True, null=True,
        validators=[validate_image], verbose_name=_("Generated image"),
    )
    is_generated = models.BooleanField(
        default=False, verbose_name=_("Generated"),
    )
    sort_order = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Sort order"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["lesson", "sort_order", "id"]
        indexes = [
            models.Index(fields=["lesson", "prompt_type"]),
            models.Index(fields=["is_generated"]),
        ]
        verbose_name = _("Lesson image prompt")
        verbose_name_plural = _("Lesson image prompts")

    def __str__(self):
        return f"{self.lesson_id} · {self.prompt_type}#{self.pk}"


# ---------------------------------------------------------------------------
# 13. CourseReview + CourseReviewQuestion + CourseReviewAttempt (Prompt 10)
# ---------------------------------------------------------------------------

REVIEW_QUESTION_SKILL_CHOICES = [
    ("vocabulary", _("Vocabulary")),
    ("grammar",    _("Grammar")),
    ("reading",    _("Reading")),
    ("listening",  _("Listening")),
    ("speaking",   _("Speaking")),
    ("writing",    _("Writing")),
]


class CourseReview(models.Model):
    """Cluster-end review for a Course (Beginner: 6 of these — one after
    each 6-unit-ish cluster).

    Unlocks for a student only when *every* required Lesson (from
    `start_unit_number` to `end_unit_number` inclusive) is marked
    `CourseLessonProgress.completed_at IS NOT NULL`.
    """

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="reviews",
        verbose_name=_("Course"),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    title_ar = models.CharField(
        max_length=200, blank=True, verbose_name=_("Title (Arabic)"),
    )
    start_unit_number = models.PositiveSmallIntegerField(
        verbose_name=_("Start unit number"),
    )
    end_unit_number = models.PositiveSmallIntegerField(
        verbose_name=_("End unit number"),
    )
    instructions = models.TextField(
        blank=True, verbose_name=_("Instructions (English)"),
    )
    instructions_ar = models.TextField(
        blank=True, verbose_name=_("Instructions (Arabic)"),
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course", "start_unit_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["course", "start_unit_number", "end_unit_number"],
                name="course_review_unique_range",
            ),
        ]
        verbose_name = _("Course review")
        verbose_name_plural = _("Course reviews")

    def __str__(self):
        return f"{self.title} (U{self.start_unit_number}-U{self.end_unit_number})"

    def is_unlocked_for(self, user) -> bool:
        """True when every unit in the range has been completed by `user`."""
        required = Lesson.objects.filter(
            course=self.course,
            order__gte=self.start_unit_number,
            order__lte=self.end_unit_number,
            is_active=True,
        )
        required_ids = list(required.values_list("id", flat=True))
        if not required_ids:
            return False
        done = CourseLessonProgress.objects.filter(
            user=user, lesson_id__in=required_ids,
            completed_at__isnull=False,
        ).count()
        return done >= len(required_ids)


class CourseReviewQuestion(models.Model):
    """One question in a CourseReview."""

    review = models.ForeignKey(
        CourseReview, on_delete=models.CASCADE, related_name="questions",
        verbose_name=_("Review"),
    )
    question_type = models.CharField(
        max_length=20, choices=QUESTION_TYPE_CHOICES,
        verbose_name=_("Question type"),
    )
    question_text = models.TextField(verbose_name=_("Question text"))
    question_text_ar = models.TextField(
        blank=True, verbose_name=_("Question text (Arabic)"),
    )
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    explanation_ar = models.TextField(blank=True)
    skill = models.CharField(
        max_length=20, choices=REVIEW_QUESTION_SKILL_CHOICES,
        default="vocabulary", verbose_name=_("Skill"),
    )
    points = models.PositiveSmallIntegerField(default=1)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["review", "order", "id"]
        indexes = [
            models.Index(fields=["review", "skill"]),
        ]
        verbose_name = _("Course review question")
        verbose_name_plural = _("Course review questions")

    def __str__(self):
        return f"{self.review_id} · Q{self.order} ({self.skill})"


class CourseReviewAttempt(models.Model):
    """One student's attempt at a CourseReview."""

    review = models.ForeignKey(
        CourseReview, on_delete=models.CASCADE, related_name="attempts",
        verbose_name=_("Review"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="course_review_attempts", verbose_name=_("Student"),
    )
    score = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name=_("Score (%)"),
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True, verbose_name=_("Feedback"))
    feedback_ar = models.TextField(
        blank=True, verbose_name=_("Feedback (Arabic)"),
    )
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["student", "review"]),
            models.Index(fields=["review", "-completed_at"]),
        ]
        verbose_name = _("Course review attempt")
        verbose_name_plural = _("Course review attempts")

    def __str__(self):
        return f"Attempt #{self.pk} · review={self.review_id} student={self.student_id}"
