"""Daily learning engine models.

A DailyLearningPlan is the per-day envelope a student opens when they
arrive on Onlenco. It holds 5–8 small DailyLearningItems plus a side
DailyGoal and a post-completion DailyLearningResult.

The schema is intentionally denormalised: items carry their rendered
question + options + correct_answer inline so a plan stays renderable
even if the underlying source (AdaptiveExercise, DictionaryEntry, etc.)
is later edited or removed.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import CEFR_CHOICES


PLAN_TYPE_CHOICES = [
    ("beginner_start",       _("Beginner start (A0)")),
    ("placement_based",      _("Placement-based")),
    ("weakness_review",      _("Weakness review")),
    ("streak_recovery",      _("Streak recovery (comeback)")),
    ("exam_preparation",     _("Exam preparation")),
    ("normal_daily_plan",    _("Normal daily plan")),
]

PLAN_STATUS_CHOICES = [
    ("pending",     _("Pending")),
    ("in_progress", _("In progress")),
    ("completed",   _("Completed")),
    ("skipped",     _("Skipped")),
]

ITEM_TYPE_CHOICES = [
    ("vocabulary",        _("Vocabulary")),
    ("grammar_tip",       _("Grammar tip")),
    ("reading",           _("Reading")),
    ("listening",         _("Listening")),
    ("speaking",          _("Speaking")),
    ("writing",           _("Writing")),
    ("quiz",              _("Quiz")),
    ("word_order",        _("Word order")),
    ("review_mistake",    _("Review mistake")),
    ("ai_tutor_practice", _("AI tutor practice")),
    ("motivation",        _("Motivation")),
]

GOAL_TYPE_CHOICES = [
    ("complete_lesson",   _("Complete a lesson")),
    ("answer_questions",  _("Answer N questions")),
    ("speaking_minutes",  _("Speak N minutes")),
    ("reading_words",     _("Read N words")),
    ("review_mistakes",   _("Review N mistakes")),
    ("maintain_streak",   _("Maintain streak")),
]

SKILL_CHOICES = [
    ("vocabulary",    "Vocabulary"),
    ("grammar",       "Grammar"),
    ("reading",       "Reading"),
    ("listening",     "Listening"),
    ("speaking",      "Speaking"),
    ("writing",       "Writing"),
    ("pronunciation", "Pronunciation"),
    ("mixed",         "Mixed"),
]


class DailyLearningPlan(models.Model):
    """One plan per (user, date). Holds N items the student should complete."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_plans",
    )
    date = models.DateField(db_index=True)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    plan_type = models.CharField(
        max_length=20, choices=PLAN_TYPE_CHOICES, default="normal_daily_plan",
    )
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    estimated_minutes = models.PositiveSmallIntegerField(default=10)
    status = models.CharField(
        max_length=15, choices=PLAN_STATUS_CHOICES, default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                name="daily_learning_unique_user_date_plan",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["plan_type"]),
            models.Index(fields=["cefr_level"]),
        ]
        verbose_name = _("Daily learning plan")
        verbose_name_plural = _("Daily learning plans")

    def __str__(self):
        return f"DailyPlan<{self.user_id}> {self.date} {self.status}"

    @property
    def progress_percent(self) -> int:
        items = self.items.all()
        total = items.count()
        if not total:
            return 0
        done = sum(1 for i in items if i.is_completed)
        return int(round(done / total * 100))


class DailyLearningItem(models.Model):
    """One task inside a DailyLearningPlan.

    Carries the rendered question/options inline so the plan is
    self-contained — the source (AdaptiveExercise, DictionaryEntry,
    etc.) is referenced via metadata["source"] but not joined at
    render time.
    """

    daily_plan = models.ForeignKey(
        DailyLearningPlan,
        on_delete=models.CASCADE,
        related_name="items",
    )
    item_type = models.CharField(max_length=20, choices=ITEM_TYPE_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    instructions = models.TextField(blank=True)
    content_text = models.TextField(blank=True)
    question = models.TextField(blank=True)
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    # Optional media so an A0 vocabulary item can carry a picture and
    # a pronunciation recording without inflating the JSON metadata
    # blob. Blank by default — templates render gracefully when missing.
    image_url = models.URLField(blank=True)
    audio_url = models.URLField(blank=True)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    skill = models.CharField(max_length=20, choices=SKILL_CHOICES, blank=True)
    difficulty_score = models.FloatField(default=0.3)
    order = models.PositiveSmallIntegerField(default=0)
    estimated_minutes = models.PositiveSmallIntegerField(default=2)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["daily_plan", "order", "id"]
        indexes = [
            models.Index(fields=["daily_plan", "order"]),
            models.Index(fields=["item_type"]),
            models.Index(fields=["is_completed"]),
        ]
        verbose_name = _("Daily learning item")
        verbose_name_plural = _("Daily learning items")

    def __str__(self):
        return f"Item<{self.id}> {self.item_type} ord={self.order}"


class DailyGoal(models.Model):
    """A measurable daily target shown to the student alongside the plan.

    Distinct from `Challenge` (which is time-boxed and opt-in). The goal
    is automatic, per-day, and resets every morning.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_goals",
    )
    date = models.DateField(db_index=True)
    goal_type = models.CharField(max_length=20, choices=GOAL_TYPE_CHOICES)
    target_value = models.PositiveIntegerField(default=1)
    current_value = models.PositiveIntegerField(default=0)
    completed = models.BooleanField(default=False)
    reward_xp = models.PositiveIntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "goal_type"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date", "goal_type"],
                name="daily_learning_unique_user_date_goal",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["completed"]),
        ]
        verbose_name = _("Daily goal")
        verbose_name_plural = _("Daily goals")

    def __str__(self):
        return f"Goal<{self.user_id}> {self.date} {self.goal_type} {self.current_value}/{self.target_value}"


class DailyLearningResult(models.Model):
    """Post-completion summary row, written when the plan is marked done."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_results",
    )
    daily_plan = models.OneToOneField(
        DailyLearningPlan,
        on_delete=models.CASCADE,
        related_name="result",
    )
    completed_items_count = models.PositiveIntegerField(default=0)
    total_items_count = models.PositiveIntegerField(default=0)
    score = models.FloatField(default=0.0)
    xp_earned = models.PositiveIntegerField(default=0)
    streak_updated = models.BooleanField(default=False)
    weaknesses_improved = models.JSONField(default=list, blank=True)
    mistakes_reviewed = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]
        verbose_name = _("Daily learning result")
        verbose_name_plural = _("Daily learning results")

    def __str__(self):
        return f"Result<{self.user_id}> plan={self.daily_plan_id} {self.completed_items_count}/{self.total_items_count}"
