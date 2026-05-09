"""Factory models — small, finite tables that drive unbounded generation.

Design intent (the "why"):
- Templates + substitution banks are stored, not the rendered questions.
- A handful of templates × richly-populated banks generate billions of
  unique surface forms on demand. We persist only the items a human/AI
  reviewer has approved into `learning_core.AdaptiveExercise`.
- `Topic` extends GrammarTopic with a parent/child hierarchy and a
  `kind` axis (grammar / vocabulary / reading / listening / writing /
  speaking / pronunciation / comprehension).
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
from accounts.models import CEFR_CHOICES


# -- Axes ------------------------------------------------------------------

KIND_CHOICES = [
    ("grammar",       "Grammar"),
    ("vocabulary",    "Vocabulary"),
    ("reading",       "Reading"),
    ("listening",     "Listening"),
    ("writing",       "Writing"),
    ("speaking",      "Speaking"),
    ("pronunciation", "Pronunciation"),
    ("comprehension", "Comprehension"),
]

QUESTION_TYPE_CHOICES = [
    ("multiple_choice",         "Multiple choice"),
    ("fill_blank",              "Fill in the blank"),
    ("correction",              "Correction"),
    ("sentence_ordering",       "Sentence ordering"),
    ("translation",             "Translation"),
    ("short_answer",            "Short answer"),
    ("reading_comprehension",   "Reading comprehension"),
    ("listening_comprehension", "Listening comprehension"),
    ("speaking_prompt",         "Speaking prompt"),
    ("writing_prompt",          "Writing prompt"),
    ("vocabulary_matching",     "Vocabulary matching"),
    ("grammar_transformation",  "Grammar transformation"),
]

DISTRACTOR_STRATEGY_CHOICES = [
    ("static",      "Static — distractors come from the template"),
    ("from_bank",   "From bank — sample wrong answers from a substitution bank"),
    ("morph",       "Morph — programmatic perturbations of the correct answer"),
    ("ai",          "AI-generated — call the LLM router"),
]


# -- Models ----------------------------------------------------------------

class Topic(models.Model):
    """Hierarchical taxonomy. A Topic may have a parent (e.g. "Verb tenses"
    → "Present simple" → "Third-person singular agreement"). Topics are the
    join axis between templates, banks, and the existing CEFR / skill model.
    """

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="children",
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Topic")
        verbose_name_plural = _("Topics")
        ordering = ["kind", "cefr_level", "name"]
        indexes = [
            models.Index(fields=["kind", "cefr_level"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["parent"]),
        ]

    def __str__(self):
        return f"[{self.kind}/{self.cefr_level or '-'}] {self.name}"

    @property
    def path(self) -> str:
        """Slash-separated breadcrumb of slugs (`grammar/tenses/present_simple`)."""
        parts = [self.slug]
        node = self.parent
        while node is not None:
            parts.append(node.slug)
            node = node.parent
        return "/".join(reversed(parts))


class SubstitutionBank(models.Model):
    """A reusable list of substitutable strings or tuples.

    `kind` examples: 'subject_singular', 'verb_regular_past', 'place', 'adj_pair'.
    `items` is a JSON list — strings *or* lists for tuple banks (e.g.
    `[["go", "went", "gone"], ["eat", "ate", "eaten"]]`)."""

    name = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=40)
    description = models.TextField(blank=True)
    items = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Substitution bank")
        verbose_name_plural = _("Substitution banks")
        ordering = ["kind", "name"]
        indexes = [
            models.Index(fields=["kind", "is_active"]),
        ]

    def __str__(self):
        return f"{self.kind}/{self.name} ({len(self.items)})"

    @property
    def size(self) -> int:
        return len(self.items or [])


class QuestionTemplate(models.Model):
    """A parametric template that the engine renders into a question dict.

    `pattern` uses `{var}` placeholders. Each placeholder name is bound to a
    SubstitutionBank by `variables` (e.g. `{"subject": "subject_singular",
    "verb": "verb_regular"}`). A single template × richly-populated banks
    yields thousands-to-millions of unique items.

    `correct_answer_expression` is a small DSL evaluated against the bound
    row from each bank — e.g. `"verb.1"` (item 1 of the verb tuple, the
    past form) or `"subject + ' + ' + verb.0"`. See template_engine for
    the supported subset.
    """

    topic = models.ForeignKey(
        Topic, on_delete=models.PROTECT, related_name="templates",
    )
    name = models.CharField(max_length=160)
    code = models.CharField(
        max_length=80, unique=True,
        help_text="Stable identifier used for deterministic codegen.",
    )
    question_type = models.CharField(max_length=24, choices=QUESTION_TYPE_CHOICES)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    pattern = models.TextField(
        help_text="Sentence template with {var} placeholders.",
    )
    variables = models.JSONField(
        default=dict,
        help_text="Map of placeholder → SubstitutionBank.name.",
    )
    correct_answer_expression = models.CharField(
        max_length=160,
        help_text="DSL expression that resolves to the correct answer "
                  "given the bound bank row.",
    )
    distractor_strategy = models.CharField(
        max_length=10, choices=DISTRACTOR_STRATEGY_CHOICES, default="from_bank",
    )
    distractor_config = models.JSONField(
        default=dict, blank=True,
        help_text="Strategy-specific config (e.g. bank name for from_bank).",
    )
    explanation_pattern = models.TextField(
        blank=True,
        help_text="Optional explanation template — same {var} syntax.",
    )
    points = models.PositiveSmallIntegerField(default=1)
    estimated_time_seconds = models.PositiveSmallIntegerField(default=30)
    difficulty_score = models.FloatField(default=0.5)
    is_active = models.BooleanField(default=True)
    version = models.PositiveSmallIntegerField(default=1)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Question template")
        verbose_name_plural = _("Question templates")
        ordering = ["topic", "name"]
        indexes = [
            models.Index(fields=["topic", "is_active"]),
            models.Index(fields=["question_type", "cefr_level"]),
        ]

    def __str__(self):
        return f"{self.code} v{self.version}"


class TrainingDataset(models.Model):
    """Header for a training dataset built from the question bank +
    student-attempt history. Rows themselves are streamed to JSONL on disk
    via `dataset_builder` — keeping millions of rows in DB would be wasteful."""

    KIND_CHOICES = [
        ("question_generation",  "Prompt → question"),
        ("error_correction",     "Wrong sentence → corrected sentence"),
        ("difficulty_estimation","Question → difficulty score"),
        ("cefr_classification",  "Question → CEFR level"),
        ("explanation_writing",  "Q+A → explanation"),
        ("rag_corpus",           "RAG corpus (chunks for retrieval)"),
    ]
    STATUS_CHOICES = [
        ("draft",     "Draft"),
        ("building",  "Building"),
        ("ready",     "Ready"),
        ("archived",  "Archived"),
    ]

    name = models.CharField(max_length=120, unique=True)
    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    description = models.TextField(blank=True)
    filters = models.JSONField(
        default=dict, blank=True,
        help_text="Source-row filters (cefr, skill, generated_by, etc.).",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    row_count = models.PositiveIntegerField(default=0)
    last_export_path = models.CharField(max_length=500, blank=True)
    last_exported_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="training_datasets",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Training dataset")
        verbose_name_plural = _("Training datasets")
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["kind", "status"]),
        ]

    def __str__(self):
        return f"{self.name} [{self.kind}] {self.status}"


class DatasetExportJob(models.Model):
    """Single export run for a TrainingDataset. Tracks progress + the
    output file path so re-runs are explicit and discoverable."""

    STATUS_CHOICES = [
        ("pending",   "Pending"),
        ("running",   "Running"),
        ("completed", "Completed"),
        ("failed",    "Failed"),
    ]

    dataset = models.ForeignKey(
        TrainingDataset, on_delete=models.CASCADE, related_name="exports",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    row_count = models.PositiveIntegerField(default=0)
    bytes_written = models.PositiveBigIntegerField(default=0)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Dataset export job")
        verbose_name_plural = _("Dataset export jobs")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["dataset", "-started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Export<{self.dataset_id}> {self.status} {self.row_count}"
