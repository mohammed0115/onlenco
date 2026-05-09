"""Exam-orchestration models. The question store is `learning_core.AdaptiveExercise`
— this app adds blueprints, exam instances, attempts, and generation-batch
tracking on top of it."""
from __future__ import annotations

from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
from accounts.models import CEFR_CHOICES
from learning_core.models import AdaptiveExercise

from . import constants as C

# The exam spec calls the unified question store `QuestionBankItem`.
# In this codebase that store is `learning_core.AdaptiveExercise` — extending
# the existing model keeps `ExerciseAttempt`/`SkillMastery`/`UserError`
# references intact instead of fragmenting the adaptive loop. The alias
# below lets external callers and the spec read naturally without
# duplicating storage.
QuestionBankItem = AdaptiveExercise


class ExamBlueprint(models.Model):
    """Defines the structure of an exam (counts, distributions, passing
    score). Blueprints are reusable templates that `assemble_exam()`
    materialises into concrete `Exam` rows."""

    name = models.CharField(max_length=160)
    exam_type = models.CharField(max_length=24, choices=C.EXAM_TYPE_CHOICES)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    skill = models.CharField(max_length=20, blank=True)
    total_questions = models.PositiveSmallIntegerField(default=10)
    duration_minutes = models.PositiveSmallIntegerField(default=15)
    difficulty_distribution = models.JSONField(default=dict, blank=True)
    skill_distribution = models.JSONField(default=dict, blank=True)
    question_type_distribution = models.JSONField(default=dict, blank=True)
    passing_score = models.PositiveSmallIntegerField(default=70)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Exam blueprint")
        verbose_name_plural = _("Exam blueprints")
        ordering = ["cefr_level", "exam_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam_type", "cefr_level", "skill"],
                name="exam_blueprint_unique_signature",
            ),
        ]
        indexes = [
            models.Index(fields=["exam_type", "cefr_level"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.cefr_level or '*'} · {self.get_exam_type_display()}"


class Exam(models.Model):
    """A concrete exam instance: blueprint + materialised list of questions."""

    title = models.CharField(max_length=200)
    blueprint = models.ForeignKey(
        ExamBlueprint,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="exams",
    )
    exam_type = models.CharField(max_length=24, choices=C.EXAM_TYPE_CHOICES)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    skill = models.CharField(max_length=20, blank=True)
    total_questions = models.PositiveSmallIntegerField(default=10)
    duration_minutes = models.PositiveSmallIntegerField(default=15)
    is_adaptive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Exam")
        verbose_name_plural = _("Exams")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["exam_type", "cefr_level"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.title or f"Exam<{self.pk}>"


class ExamQuestion(models.Model):
    """Through-model that pins an AdaptiveExercise to an Exam with order
    + per-exam point value."""

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    question = models.ForeignKey(
        AdaptiveExercise, on_delete=models.PROTECT, related_name="exam_questions",
    )
    order = models.PositiveSmallIntegerField(default=0)
    points = models.PositiveSmallIntegerField(default=1)

    class Meta:
        verbose_name = _("Exam question")
        verbose_name_plural = _("Exam questions")
        ordering = ["exam", "order"]
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "question"], name="examquestion_unique_question_per_exam",
            ),
        ]

    def __str__(self):
        return f"ExQ<{self.exam_id}> #{self.order} q={self.question_id}"


class ExamAttempt(models.Model):
    """A student's attempt at an Exam."""

    STATUS_CHOICES = [
        ("in_progress", "In progress"),
        ("submitted", "Submitted"),
        ("graded", "Graded"),
        ("expired", "Expired"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="exam_attempts",
    )
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(default=0.0)
    percentage = models.FloatField(default=0.0)
    passed = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="in_progress")
    cefr_result = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    feedback = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Exam attempt")
        verbose_name_plural = _("Exam attempts")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["exam", "-started_at"]),
        ]

    def __str__(self):
        return f"Attempt<{self.user_id}> exam={self.exam_id} {self.status}"


class ExamAnswer(models.Model):
    """One answer recorded for a question in an exam attempt."""

    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name="answers",
    )
    question = models.ForeignKey(
        AdaptiveExercise, on_delete=models.PROTECT, related_name="exam_answers",
    )
    user_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    score = models.FloatField(default=0.0)
    feedback = models.TextField(blank=True)
    error_analysis = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Exam answer")
        verbose_name_plural = _("Exam answers")
        ordering = ["attempt", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="examanswer_unique_question_per_attempt",
            ),
        ]

    def __str__(self):
        return f"Ans<{self.attempt_id}> q={self.question_id} ok={self.is_correct}"


class QuestionGenerationBatch(models.Model):
    """Tracks a single bulk-generation run so it can resume after a crash."""

    batch_id = models.CharField(max_length=80, unique=True)
    target_count = models.PositiveIntegerField()
    generated_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    cefr_level = models.CharField(max_length=2, blank=True)
    skill = models.CharField(max_length=20, blank=True)
    status = models.CharField(
        max_length=10, choices=C.BATCH_STATUS_CHOICES, default=C.BATCH_PENDING,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Question generation batch")
        verbose_name_plural = _("Question generation batches")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status", "-started_at"]),
            models.Index(fields=["cefr_level", "skill"]),
        ]

    def __str__(self):
        return f"Batch<{self.batch_id}> {self.status} {self.generated_count}/{self.target_count}"
