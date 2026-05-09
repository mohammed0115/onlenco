"""Blueprint-driven question factory.

Architectural intent:
- A `QuestionBlueprint` is a *contract* — what the question looks like at
  the structural level (pattern, expected answer DSL, variable schema).
- A `QuestionVariableSet` is a concrete bundle of variable values — many
  sets per blueprint, possibly thousands per CEFR/topic.
- A `GeneratedQuestion` is the rendered output, sitting in a staging
  table for review before promotion to `learning_core.AdaptiveExercise`.
- A `GenerationBatch` tracks one bulk-generation run for resumability
  + auditability.

Why separate `GeneratedQuestion` from `learning_core.AdaptiveExercise`:
- Lets human reviewers iterate before items hit production lessons.
- Carries `approved_for_training` so we know which rows are safe to
  ship to fine-tuning datasets — independent of `is_active`.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
from accounts.models import CEFR_CHOICES
from learning_core.models import GrammarTopic

from . import constants as C


class QuestionBlueprint(models.Model):
    """A re-usable, parametric blueprint for a class of questions."""

    code = models.CharField(
        max_length=80, unique=True,
        help_text="Stable identifier (e.g. 'gr-A1-presimple-3sg').",
    )
    title = models.CharField(max_length=160)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    skill = models.CharField(max_length=20, choices=C.SKILL_CHOICES, blank=True)
    question_type = models.CharField(
        max_length=24, choices=C.QUESTION_TYPE_CHOICES,
    )
    grammar_topic = models.ForeignKey(
        GrammarTopic, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="qf_blueprints",
    )
    vocabulary_topic = models.CharField(
        max_length=80, blank=True,
        help_text="Free-text vocabulary topic (no model exists yet).",
    )
    difficulty_min = models.FloatField(default=0.0)
    difficulty_max = models.FloatField(default=1.0)
    template_pattern = models.TextField(
        help_text="Sentence template with {var} placeholders.",
    )
    expected_answer_pattern = models.CharField(
        max_length=200,
        help_text="DSL expression resolving to the correct answer.",
    )
    explanation_pattern = models.TextField(blank=True)
    variables_schema = models.JSONField(
        default=dict, blank=True,
        help_text="Schema describing each variable (inline lists or bank refs).",
    )
    generation_strategy = models.CharField(
        max_length=10, choices=C.GEN_STRATEGY_CHOICES, default=C.GEN_TEMPLATE,
    )
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Question blueprint")
        verbose_name_plural = _("Question blueprints")
        ordering = ["cefr_level", "skill", "code"]
        indexes = [
            models.Index(fields=["cefr_level", "skill"]),
            models.Index(fields=["question_type", "cefr_level"]),
            models.Index(fields=["generation_strategy"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.code} [{self.cefr_level or '-'}/{self.skill or '-'}]"


class QuestionVariableSet(models.Model):
    """Concrete bundle of variable values bound to a blueprint.

    `variables` is a dict where each key matches a placeholder in the
    blueprint's `template_pattern`. Values may be strings, lists, or
    list-of-tuples for inflected verbs / adjective tuples.
    """

    blueprint = models.ForeignKey(
        QuestionBlueprint, on_delete=models.CASCADE, related_name="variable_sets",
    )
    variables = models.JSONField(default=dict)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    skill = models.CharField(max_length=20, choices=C.SKILL_CHOICES, blank=True)
    grammar_topic = models.ForeignKey(
        GrammarTopic, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="qf_variable_sets",
    )
    difficulty_score = models.FloatField(default=0.5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Question variable set")
        verbose_name_plural = _("Question variable sets")
        ordering = ["blueprint", "id"]
        indexes = [
            models.Index(fields=["blueprint", "is_active"]),
            models.Index(fields=["cefr_level", "skill"]),
        ]

    def __str__(self):
        return f"VS<{self.blueprint_id}> #{self.id}"


class GeneratedQuestion(models.Model):
    """Rendered question — review staging table before promotion to
    the live question bank (`learning_core.AdaptiveExercise`)."""

    GENERATED_BY_CHOICES = [
        (C.GEN_TEMPLATE, "Template"),
        (C.GEN_AI,       "AI"),
        (C.GEN_HYBRID,   "Hybrid"),
        (C.GEN_IMPORTED, "Imported"),
    ]

    blueprint = models.ForeignKey(
        QuestionBlueprint, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="generated_questions",
    )
    code = models.CharField(max_length=160, unique=True)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    skill = models.CharField(max_length=20, choices=C.SKILL_CHOICES, blank=True)
    question_type = models.CharField(max_length=24, choices=C.QUESTION_TYPE_CHOICES)
    grammar_topic = models.ForeignKey(
        GrammarTopic, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="qf_generated",
    )
    vocabulary_topic = models.CharField(max_length=80, blank=True)
    difficulty_score = models.FloatField(default=0.5)
    question_text = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField()
    acceptable_answers = models.JSONField(default=list, blank=True)
    explanation = models.TextField(blank=True)
    feedback_correct = models.TextField(blank=True)
    feedback_wrong = models.TextField(blank=True)
    generated_by = models.CharField(
        max_length=10, choices=GENERATED_BY_CHOICES, default=C.GEN_TEMPLATE,
    )
    quality_score = models.PositiveSmallIntegerField(default=0)
    content_hash = models.CharField(
        max_length=40, db_index=True,
        help_text="SHA-1 of normalised text — used for dedup.",
    )
    is_active = models.BooleanField(default=True)
    is_reviewed = models.BooleanField(default=False)
    approved_for_training = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Generated question")
        verbose_name_plural = _("Generated questions")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["cefr_level", "skill"]),
            models.Index(fields=["question_type", "cefr_level"]),
            models.Index(fields=["generated_by"]),
            models.Index(fields=["is_active", "is_reviewed"]),
            models.Index(fields=["approved_for_training"]),
            models.Index(fields=["quality_score"]),
            models.Index(fields=["content_hash"]),
        ]

    def __str__(self):
        return f"{self.code} q={self.quality_score} reviewed={self.is_reviewed}"


class QuestionSeed(models.Model):
    """A *recipe* for a question, not the rendered question itself.

    The whole point of this row: store O(seeds-actually-used), never
    O(seeds-possible). A seed_key + the deterministic renderer is enough
    to reproduce the question text, options, and correct answer at any
    time — so we only need a row when the seed has been *manifested*
    (a student answered it, a reviewer approved it, an exam used it,
    etc.).

    Format of seed_key (today): ``sd:<blueprint.code>:<variant>``.
    `variant` is a 32-bit integer that the renderer feeds into the same
    deterministic seed used during bulk generation, so the same seed_key
    always reproduces the same item bytes-for-bytes.
    """

    seed_key = models.CharField(max_length=80, unique=True)
    blueprint = models.ForeignKey(
        QuestionBlueprint, on_delete=models.PROTECT,
        related_name="seeds",
    )
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    skill = models.CharField(max_length=20, choices=C.SKILL_CHOICES, blank=True)
    grammar_topic = models.ForeignKey(
        GrammarTopic, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="qf_seeds",
    )
    difficulty_score = models.FloatField(default=0.5)
    variable_state = models.JSONField(
        default=dict, blank=True,
        help_text="The exact variable bindings used at render time.",
    )
    content_hash = models.CharField(
        max_length=40, db_index=True,
        help_text="SHA-1 of normalised text — used for user-level dedup.",
    )
    generated_count = models.PositiveIntegerField(
        default=1,
        help_text="How many times this seed has been served (across all users).",
    )
    last_used_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Question seed")
        verbose_name_plural = _("Question seeds")
        ordering = ["-last_used_at"]
        indexes = [
            models.Index(fields=["blueprint", "-last_used_at"]),
            models.Index(fields=["cefr_level", "skill"]),
            models.Index(fields=["content_hash"]),
        ]

    def __str__(self):
        return f"Seed<{self.seed_key}>"


class UserSeedHistory(models.Model):
    """Records that a user has *seen* a particular seed — which lets the
    on-demand service avoid re-serving the same content.

    We also stamp `content_hash` here directly (denormalised from
    `seed.content_hash`) so the dedup query is one indexed lookup
    instead of a join."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="qf_seed_history",
    )
    seed = models.ForeignKey(
        QuestionSeed, on_delete=models.CASCADE, related_name="user_views",
    )
    content_hash = models.CharField(max_length=40, db_index=True)
    answered = models.BooleanField(default=False)
    is_correct = models.BooleanField(null=True, blank=True)
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("User seed history")
        verbose_name_plural = _("User seed histories")
        ordering = ["-seen_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "seed"],
                name="qf_user_seed_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "content_hash"]),
            models.Index(fields=["user", "-seen_at"]),
        ]

    def __str__(self):
        return f"UserSeen<{self.user_id}> seed={self.seed_id} ans={self.answered}"


class GenerationBatch(models.Model):
    """One bulk-generation run; resumable + auditable."""

    batch_id = models.CharField(max_length=80, unique=True)
    target_count    = models.PositiveIntegerField()
    generated_count = models.PositiveIntegerField(default=0)
    accepted_count  = models.PositiveIntegerField(default=0)
    rejected_count  = models.PositiveIntegerField(default=0)
    duplicate_count = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=10, choices=C.BATCH_STATUS_CHOICES, default=C.BATCH_PENDING,
    )
    strategy = models.CharField(
        max_length=10, choices=C.GEN_STRATEGY_CHOICES, default=C.GEN_TEMPLATE,
    )
    cefr_level = models.CharField(max_length=2, blank=True)
    skill = models.CharField(max_length=20, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Generation batch")
        verbose_name_plural = _("Generation batches")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status", "-started_at"]),
            models.Index(fields=["cefr_level", "skill"]),
            models.Index(fields=["strategy"]),
        ]

    def __str__(self):
        return (f"Batch<{self.batch_id}> {self.status} "
                f"{self.accepted_count}/{self.target_count}")
