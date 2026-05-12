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
    ("archived",       _("Archived")),
]
LESSON_STATUS_CHOICES = [
    ("draft",          _("Draft")),
    ("pending_review", _("Pending review")),
    ("published",      _("Published")),
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
    slug = models.SlugField(max_length=220, unique=True, verbose_name=_("Slug"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
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
    prerequisites = models.TextField(blank=True, verbose_name=_("Prerequisites"))
    is_free = models.BooleanField(default=False, verbose_name=_("Free"))
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

    def __str__(self):
        return self.title


# ---------------------------------------------------------------------------
# 3. CourseUnit
# ---------------------------------------------------------------------------

class CourseUnit(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="units",
        verbose_name=_("Course"),
    )
    title = models.CharField(max_length=200, verbose_name=_("Title"))
    order = models.PositiveSmallIntegerField(default=0, verbose_name=_("Order"))
    description = models.TextField(blank=True, verbose_name=_("Description"))

    class Meta:
        ordering = ["course", "order", "id"]
        verbose_name = _("Course unit")
        verbose_name_plural = _("Course units")

    def __str__(self):
        return f"{self.course.title} — {self.title}"


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

    def clean(self):
        super().clean()
        if self.video_url:
            validate_video_url(self.video_url)

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
    passing_score = models.PositiveSmallIntegerField(
        default=70, verbose_name=_("Passing score (%)"),
    )
    time_limit_minutes = models.PositiveSmallIntegerField(
        default=0, verbose_name=_("Time limit (minutes)"),
        help_text=_("0 = no limit"),
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Active"))

    class Meta:
        verbose_name = _("Lesson quiz")
        verbose_name_plural = _("Lesson quizzes")

    def __str__(self):
        return f"Quiz: {self.lesson.title}"


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
    options = models.JSONField(
        default=list, blank=True, verbose_name=_("Options"),
    )
    correct_answer = models.TextField(
        blank=True, verbose_name=_("Correct answer"),
    )
    explanation = models.TextField(blank=True, verbose_name=_("Explanation"))
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
        if self.question_type == "multiple_choice":
            opts = list(self.options or [])
            if len(opts) < 2:
                raise ValidationError(
                    _("Multiple-choice questions need at least 2 options.")
                )
            if self.correct_answer and self.correct_answer not in opts:
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
