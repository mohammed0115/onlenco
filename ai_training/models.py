"""Training-data records.

Architectural intent
--------------------
- `AITrainingExample` is the unit row — one per (input, output) pair
  destined for fine-tuning. Schema-free `input`/`output` JSON because
  every task type has different shapes.
- `DatasetBuild` tracks one build run (filters, source, quality
  decisions). Re-runs create new builds; they are auditable.
- `DatasetExport` records one materialisation to disk (JSONL or CSV).
  Multiple exports per build are allowed (e.g. one per split).
- `DatasetQualityReport` is the human-readable summary attached to a
  build — counts, distributions, filter outcomes.

We deliberately keep the AITrainingExample row count small relative to
the source data: `dataset_quality_filter` rejects unreviewed,
low-quality, duplicate, and PII-tainted candidates *before* a row is
written. Volume comes from approved sources, not loose collection.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
from accounts.models import CEFR_CHOICES

from . import constants as C


class AITrainingExample(models.Model):
    """One (input, output) example for fine-tuning."""

    task_type = models.CharField(max_length=24, choices=C.TASK_TYPE_CHOICES)
    input = models.JSONField(default=dict)
    output = models.JSONField(default=dict)

    # Provenance — useful for auditing + revoking examples by source.
    source_type = models.CharField(
        max_length=40, blank=True,
        help_text="e.g. 'AdaptiveExercise', 'UserError', 'TutorMessage'.",
    )
    source_id = models.PositiveIntegerField(null=True, blank=True)

    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    skill = models.CharField(max_length=20, blank=True)
    quality_score = models.PositiveSmallIntegerField(default=0)
    is_approved = models.BooleanField(default=True)
    language = models.CharField(max_length=2, default="en")
    content_hash = models.CharField(
        max_length=40, db_index=True,
        help_text="SHA-1 of (task_type + input + output) — used for dedup.",
    )
    split = models.CharField(
        max_length=10, choices=C.SPLIT_CHOICES, blank=True,
        help_text="Deterministic train/val/test bucket (set by exporter).",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Aitraining example")
        verbose_name_plural = _("Aitraining examples")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "content_hash"],
                name="aitex_unique_task_hash",
            ),
        ]
        indexes = [
            models.Index(fields=["task_type", "split"]),
            models.Index(fields=["task_type", "is_approved"]),
            models.Index(fields=["cefr_level", "skill"]),
            models.Index(fields=["quality_score"]),
        ]

    def __str__(self):
        return f"Example<{self.id}> {self.task_type} q={self.quality_score}"


class DatasetBuild(models.Model):
    """One build run. Filters + source live in the metadata JSON; the
    counts are first-class so dashboards can read them with one query."""

    name = models.CharField(max_length=120, unique=True)
    task_type = models.CharField(max_length=24, choices=C.TASK_TYPE_CHOICES)
    status = models.CharField(
        max_length=10, choices=C.BUILD_STATUS_CHOICES, default=C.BUILD_PENDING,
    )
    filters = models.JSONField(default=dict, blank=True)
    example_count   = models.PositiveIntegerField(default=0)
    rejected_count  = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    private_data_count = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Dataset build")
        verbose_name_plural = _("Dataset builds")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["task_type", "-started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Build<{self.name}> {self.task_type} {self.status}"


class DatasetExport(models.Model):
    """One materialisation of a build to disk."""

    build = models.ForeignKey(
        DatasetBuild, on_delete=models.CASCADE, related_name="exports",
    )
    format = models.CharField(max_length=8, choices=C.FORMAT_CHOICES,
                              default=C.FORMAT_JSONL)
    split = models.CharField(
        max_length=10, default=C.SPLIT_ALL,
        help_text="One of 'train' / 'validation' / 'test' / 'all'.",
    )
    file_path = models.CharField(max_length=500, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    bytes_written = models.PositiveBigIntegerField(default=0)
    status = models.CharField(
        max_length=10, choices=C.BUILD_STATUS_CHOICES, default=C.BUILD_PENDING,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Dataset export")
        verbose_name_plural = _("Dataset exports")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["build", "-started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Export<{self.id}> {self.build_id} {self.format}/{self.split}"


class EvaluationRun(models.Model):
    """One scored evaluation pass over a dataset's `test` split.

    The eval loop loads `AITrainingExample` rows where `split='test'`
    for the named build, sends each through the routed provider, and
    scores the predicted output against the stored ground-truth.

    Carries provider attribution (`provider`, `model_version`) so a
    dashboard can chart "local vs OpenAI vs rules" accuracy over time
    and spot regressions when a freshly-trained local model under-
    performs the previous one."""

    name = models.CharField(max_length=120, unique=True)
    build = models.ForeignKey(
        DatasetBuild, on_delete=models.CASCADE, related_name="evaluations",
    )
    task_type = models.CharField(max_length=24, choices=C.TASK_TYPE_CHOICES)
    provider = models.CharField(
        max_length=20, blank=True,
        help_text="Provider tested (e.g. 'rules', 'local_llm', 'openai').",
    )
    model_version = models.CharField(max_length=80, blank=True)

    total_examples = models.PositiveIntegerField(default=0)
    correct_count  = models.PositiveIntegerField(default=0)
    incorrect_count = models.PositiveIntegerField(default=0)
    skipped_count  = models.PositiveIntegerField(default=0)
    accuracy = models.FloatField(default=0.0)
    mean_absolute_error = models.FloatField(
        null=True, blank=True,
        help_text="Filled for regression tasks (e.g. difficulty_estimation).",
    )
    avg_latency_ms = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=10, choices=C.BUILD_STATUS_CHOICES, default=C.BUILD_PENDING,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Evaluation run")
        verbose_name_plural = _("Evaluation runs")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["task_type", "-started_at"]),
            models.Index(fields=["build", "-started_at"]),
            models.Index(fields=["provider"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return (f"Eval<{self.name}> {self.task_type}/{self.provider} "
                f"acc={self.accuracy:.2f}")


class DatasetQualityReport(models.Model):
    """Summary metrics + distributions for a finished build."""

    build = models.OneToOneField(
        DatasetBuild, on_delete=models.CASCADE, related_name="quality_report",
    )
    total_examples           = models.PositiveIntegerField(default=0)
    avg_quality_score        = models.FloatField(default=0.0)
    distribution_by_cefr     = models.JSONField(default=dict, blank=True)
    distribution_by_skill    = models.JSONField(default=dict, blank=True)
    distribution_by_task_type = models.JSONField(default=dict, blank=True)
    duplicates_removed       = models.PositiveIntegerField(default=0)
    private_data_filtered    = models.PositiveIntegerField(default=0)
    low_quality_filtered     = models.PositiveIntegerField(default=0)
    issues = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Dataset quality report")
        verbose_name_plural = _("Dataset quality reports")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report<{self.build_id}> n={self.total_examples}"
