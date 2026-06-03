from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import CEFR_CHOICES


SKILL_CATEGORY_CHOICES = [
    ("grammar", "Grammar"),
    ("vocabulary", "Vocabulary"),
    ("pronunciation", "Pronunciation"),
    ("listening", "Listening"),
    ("reading", "Reading"),
    ("writing", "Writing"),
    ("speaking", "Speaking"),
]

ERROR_TYPE_CHOICES = [
    ("grammar", "Grammar"),
    ("spelling", "Spelling"),
    ("vocabulary", "Vocabulary"),
    ("punctuation", "Punctuation"),
    ("word_order", "Word order"),
    ("pronunciation", "Pronunciation"),
    ("comprehension", "Comprehension"),
]

ERROR_SOURCE_CHOICES = [
    ("placement", "Placement"),
    ("quiz", "Quiz"),
    ("tutor", "Tutor"),
    ("writing", "Writing"),
    ("speaking", "Speaking"),
    ("exercise", "Exercise"),
]

WEAKNESS_STATUS_CHOICES = [
    ("active", "Active"),
    ("improving", "Improving"),
    ("resolved", "Resolved"),
]

QUESTION_TYPE_CHOICES = [
    ("multiple_choice", "Multiple choice"),
    ("fill_blank", "Fill in the blank"),
    ("correction", "Correction"),
    ("sentence_building", "Sentence building"),
    ("translation", "Translation"),
    ("short_answer", "Short answer"),
    ("picture_word", "Picture → word"),
    ("picture_verb", "Picture → verb"),
    ("picture_adjective", "Picture → adjective"),
]

RECOMMENDATION_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("active", "Active"),
    ("completed", "Completed"),
    ("dismissed", "Dismissed"),
    ("replaced", "Replaced"),
]

RECOMMENDATION_TYPE_CHOICES = [
    ("practice_skill", "Practice skill"),
    ("review_topic", "Review grammar topic"),
    ("continue_lesson", "Continue lesson"),
    ("ask_tutor", "Ask AI tutor"),
    ("retake_placement", "Retake placement"),
    ("speaking_drill", "Speaking drill"),
    ("writing_drill", "Writing drill"),
    ("weekly_assessment", "Take weekly assessment"),
]

WEEKLY_ASSESSMENT_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("in_progress", "In progress"),
    ("completed", "Completed"),
    ("expired", "Expired"),
]


class Skill(models.Model):
    """A teachable skill (e.g. Grammar at B1, Listening at A2).

    Phase 6 added the `code` (URL-safe identifier — "greetings",
    "to_be_names") + bilingual titles/descriptions + sort_order. The
    legacy `name`+`category`+`cefr_level` triplet stays as a backward-
    compatible secondary key so existing rows keep working.
    """

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=SKILL_CATEGORY_CHOICES)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    description = models.TextField(blank=True)
    # Phase 6: machine-friendly identifier used by question metadata,
    # the resolver, and tests. Nullable so existing rows aren't broken
    # by migration — `seed_learning_skills` upserts by `code` when set.
    code = models.SlugField(
        max_length=80, blank=True, null=True, unique=True,
        verbose_name=_("Skill code"),
        help_text=_("snake_case identifier — e.g. 'greetings'."),
    )
    title_en = models.CharField(max_length=120, blank=True)
    title_ar = models.CharField(max_length=120, blank=True)
    description_ar = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "category", "cefr_level", "name"]
        indexes = [
            models.Index(fields=["category", "cefr_level"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["code"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "category", "cefr_level"],
                name="unique_skill_name_category_level",
            )
        ]
        verbose_name = _("Skill")
        verbose_name_plural = _("Skills")

    def __str__(self):
        return f"{self.get_category_display()} · {self.name}"

    @property
    def display_title(self) -> str:
        return self.title_en or self.name


class GrammarTopic(models.Model):
    """A specific grammar topic (e.g. Present Perfect, Articles)."""

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    description = models.TextField(blank=True)
    related_skills = models.ManyToManyField(
        Skill, related_name="grammar_topics", blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cefr_level", "name"]
        indexes = [
            models.Index(fields=["cefr_level"]),
            models.Index(fields=["is_active"]),
        ]
        verbose_name = _("Grammar topic")
        verbose_name_plural = _("Grammar topics")

    def __str__(self):
        return f"[{self.cefr_level or '-'}] {self.name}"


class StudentLearningProfile(models.Model):
    """Per-student adaptive learning state. One profile per user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_profile",
    )
    current_cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True
    )
    theta_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(-3.0), MaxValueValidator(3.0)],
    )
    learning_speed = models.FloatField(default=1.0)
    confidence_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    last_activity_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["current_cefr_level"]),
            models.Index(fields=["theta_score"]),
        ]
        verbose_name = _("Student learning profile")
        verbose_name_plural = _("Student learning profiles")

    def __str__(self):
        return f"LearningProfile<{self.user_id}> θ={self.theta_score:.2f}"


CONFIDENCE_LEVEL_CHOICES = [
    ("new",       _("New")),
    ("learning",  _("Learning")),
    ("improving", _("Improving")),
    ("strong",    _("Strong")),
    ("mastered",  _("Mastered")),
]


def confidence_for(score: float) -> str:
    """Compute confidence band from a 0-100 score (Phase 6 rule)."""
    if score >= 90:
        return "mastered"
    if score >= 71:
        return "strong"
    if score >= 46:
        return "improving"
    if score >= 21:
        return "learning"
    return "new"


class SkillMastery(models.Model):
    """Per-(user, skill) mastery tracking.

    Phase 6 added: `confidence_level` (band derived from score),
    `current_streak_correct/wrong` (consecutive answers in either
    direction), and `next_review_at` (when this skill is due for
    practice — used by the smart review queue).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="skill_masteries",
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="masteries"
    )
    mastery_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )
    confidence_level = models.CharField(
        max_length=12, choices=CONFIDENCE_LEVEL_CHOICES, default="new",
    )
    attempts_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    current_streak_correct = models.PositiveIntegerField(default=0)
    current_streak_wrong   = models.PositiveIntegerField(default=0)
    last_practiced_at = models.DateTimeField(null=True, blank=True)
    next_review_at    = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-mastery_score", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "skill"], name="unique_user_skill_mastery"
            )
        ]
        indexes = [
            models.Index(fields=["user", "skill"]),
            models.Index(fields=["mastery_score"]),
            models.Index(fields=["next_review_at"]),
        ]
        verbose_name = _("Skill mastery")
        verbose_name_plural = _("Skill masteries")

    def __str__(self):
        return f"{self.user_id}·{self.skill_id} {self.mastery_score:.1f}%"


class UserError(models.Model):
    """A single language error produced by a student.

    Created by the Error Analysis Engine. Many UserErrors → one UserWeakness.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_errors",
    )
    source_type = models.CharField(max_length=20, choices=ERROR_SOURCE_CHOICES)
    original_text = models.TextField(blank=True)
    corrected_text = models.TextField(blank=True)
    error_type = models.CharField(max_length=20, choices=ERROR_TYPE_CHOICES)
    grammar_topic = models.ForeignKey(
        GrammarTopic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_errors",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_errors",
    )
    severity = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    explanation = models.TextField(blank=True)
    ai_confidence = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["error_type"]),
            models.Index(fields=["source_type"]),
        ]
        verbose_name = _("User error")
        verbose_name_plural = _("User errors")

    def __str__(self):
        return f"Err<{self.user_id}> {self.error_type} sev={self.severity}"


class UserWeakness(models.Model):
    """Aggregated weakness profile per (user, skill, grammar_topic)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weaknesses",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weaknesses",
    )
    grammar_topic = models.ForeignKey(
        GrammarTopic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weaknesses",
    )
    weakness_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )
    frequency = models.PositiveIntegerField(default=0)
    severity_average = models.FloatField(default=0.0)
    recency_score = models.FloatField(default=0.0)
    priority_score = models.FloatField(default=0.0)
    status = models.CharField(
        max_length=15, choices=WEAKNESS_STATUS_CHOICES, default="active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority_score", "-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "skill", "grammar_topic"],
                name="unique_user_skill_topic_weakness",
            )
        ]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["priority_score"]),
            models.Index(fields=["weakness_score"]),
        ]
        verbose_name = _("User weakness")
        verbose_name_plural = _("User weaknesses")

    def __str__(self):
        bits = [str(self.user_id)]
        if self.skill_id:
            bits.append(f"sk={self.skill_id}")
        if self.grammar_topic_id:
            bits.append(f"gt={self.grammar_topic_id}")
        return f"Weakness<{' '.join(bits)}> p={self.priority_score:.1f}"


class AdaptiveExercise(models.Model):
    """A generated or curated exercise the student can attempt."""

    topic = models.ForeignKey(
        GrammarTopic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercises",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exercises",
    )
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    difficulty_score = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    question_type = models.CharField(max_length=32, choices=QUESTION_TYPE_CHOICES)
    question = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField()
    explanation = models.TextField(blank=True)
    generated_by_ai = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    # Question-bank fields. Added by the exams app so AdaptiveExercise can
    # serve as the single 300k+ item store without duplicating models.
    code = models.CharField(
        max_length=160, blank=True, db_index=True,
        help_text="Deterministic identifier — enables idempotent bulk generation.",
    )
    text_hash = models.CharField(
        max_length=40, blank=True, db_index=True,
        help_text="SHA-1 of normalised question text — used for duplicate detection.",
    )
    quality_score = models.PositiveSmallIntegerField(
        default=0,
        help_text="0..100. Computed by question_quality service.",
    )
    is_active = models.BooleanField(default=True)
    is_reviewed = models.BooleanField(default=False)
    acceptable_answers = models.JSONField(default=list, blank=True)
    feedback_correct = models.TextField(blank=True)
    feedback_wrong = models.TextField(blank=True)
    estimated_time_seconds = models.PositiveSmallIntegerField(default=30)
    points = models.PositiveSmallIntegerField(default=1)
    language = models.CharField(max_length=2, default="en")
    GENERATED_BY_CHOICES = [
        ("template", "Template"),
        ("ai", "AI"),
        ("manual", "Manual"),
        ("imported", "Imported"),
    ]
    generated_by = models.CharField(
        max_length=10, choices=GENERATED_BY_CHOICES, default="manual",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["cefr_level"]),
            models.Index(fields=["question_type"]),
            models.Index(fields=["difficulty_score"]),
            models.Index(fields=["generated_by_ai"]),
            models.Index(fields=["is_active", "is_reviewed"]),
            models.Index(fields=["cefr_level", "question_type", "is_active"]),
            models.Index(fields=["generated_by"]),
            models.Index(fields=["quality_score"]),
            # Partial index covering the exam-assembly hot path:
            # SELECT … WHERE is_active AND is_reviewed AND cefr_level=? AND question_type=?
            # On Postgres this is much smaller than a 300k×4-column index
            # because it indexes only the rows the assembler will ever look at.
            models.Index(
                fields=["cefr_level", "question_type"],
                condition=models.Q(is_active=True, is_reviewed=True),
                name="adex_assembly_hot_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(code__gt=""),
                name="adaptive_exercise_unique_code",
            ),
        ]
        verbose_name = _("Adaptive exercise")
        verbose_name_plural = _("Adaptive exercises")

    def __str__(self):
        return f"Ex<{self.id}> {self.question_type} d={self.difficulty_score:.2f}"


class ExerciseAttempt(models.Model):
    """Records a student's attempt at an AdaptiveExercise."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="exercise_attempts",
    )
    exercise = models.ForeignKey(
        AdaptiveExercise, on_delete=models.CASCADE, related_name="attempts"
    )
    user_answer = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    time_spent_seconds = models.PositiveIntegerField(default=0)
    feedback = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["is_correct"]),
        ]
        verbose_name = _("Exercise attempt")
        verbose_name_plural = _("Exercise attempts")

    def __str__(self):
        return f"Att<{self.user_id}> ex={self.exercise_id} ok={self.is_correct}"


class LearningRecommendation(models.Model):
    """A next-step suggestion produced by the recommendation engine."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_recommendations",
    )
    recommendation_type = models.CharField(
        max_length=30, choices=RECOMMENDATION_TYPE_CHOICES
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    priority = models.FloatField(default=0.0)
    related_skill = models.ForeignKey(
        Skill,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
    )
    related_weakness = models.ForeignKey(
        UserWeakness,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendations",
    )
    status = models.CharField(
        max_length=15, choices=RECOMMENDATION_STATUS_CHOICES, default="pending"
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["priority"]),
        ]
        verbose_name = _("Learning recommendation")
        verbose_name_plural = _("Learning recommendations")

    def __str__(self):
        return f"Rec<{self.user_id}> {self.recommendation_type} p={self.priority:.1f}"


ASSESSMENT_KIND_CHOICES = [
    ("daily", "Daily check-in"),
    ("weekly", "Weekly assessment"),
    ("milestone", "Milestone"),
]


class WeeklyAssessment(models.Model):
    """A periodic assessment.

    Despite the legacy class name, this model hosts both *daily* (short,
    one per day, ~5 questions) and *weekly* (every 3 lessons, ~10 questions)
    formats. The `kind` field discriminates. On completion, theta +
    weaknesses + recommendations are refreshed.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_assessments",
    )
    kind = models.CharField(
        max_length=15, choices=ASSESSMENT_KIND_CHOICES, default="weekly"
    )
    triggered_after_lessons_count = models.PositiveIntegerField(default=0)
    exercises = models.ManyToManyField(
        AdaptiveExercise, related_name="weekly_assessments", blank=True
    )
    status = models.CharField(
        max_length=15, choices=WEEKLY_ASSESSMENT_STATUS_CHOICES, default="pending"
    )
    score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "kind", "-created_at"]),
            models.Index(fields=["-created_at"]),
        ]
        verbose_name = _("Weekly assessment")
        verbose_name_plural = _("Weekly assessments")

    def __str__(self):
        return f"{self.kind.title()}Asmt<{self.user_id}> {self.status} score={self.score:.0f}"


# ---------------------------------------------------------------------------
# Phase 6 — StudentMistake + MasteryEvent
# ---------------------------------------------------------------------------

MISTAKE_TYPE_CHOICES = [
    ("wrong_choice", _("Wrong choice")),
    ("spelling",     _("Spelling")),
    ("word_order",   _("Word order")),
    ("grammar",      _("Grammar")),
    ("listening",    _("Listening")),
    ("speaking",     _("Speaking")),
    ("translation",  _("Translation")),
    ("unknown",      _("Unknown")),
]

MISTAKE_SEVERITY_CHOICES = [
    ("low",    _("Low")),
    ("medium", _("Medium")),
    ("high",   _("High")),
]


class StudentMistake(models.Model):
    """One row per (user, question) — created the first time a student
    gets a question wrong, then UPDATED (not duplicated) on every
    subsequent wrong attempt.

    `UserError` (above) is the AI-tagged generic table — Phase 6 keeps
    this separate so the rule-based engine has a focused, simple ledger
    the review scheduler can lean on without depending on the AI
    pipeline.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_mistakes",
    )
    question = models.ForeignKey(
        "courses.LessonQuestion",
        on_delete=models.CASCADE,
        related_name="student_mistakes",
    )
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="student_mistakes",
    )
    skill = models.ForeignKey(
        Skill, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="student_mistakes",
    )
    challenge_answer = models.ForeignKey(
        "courses.ChallengeAnswer",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="student_mistakes",
    )

    mistake_type = models.CharField(
        max_length=20, choices=MISTAKE_TYPE_CHOICES, default="unknown",
    )
    severity = models.CharField(
        max_length=8, choices=MISTAKE_SEVERITY_CHOICES, default="medium",
    )

    user_answer = models.TextField(blank=True)
    correct_answer = models.TextField(blank=True)
    explanation_en = models.TextField(blank=True)
    explanation_ar = models.TextField(blank=True)

    review_count = models.PositiveIntegerField(default=0)
    mastered = models.BooleanField(default=False)
    next_review_at = models.DateTimeField(null=True, blank=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "mastered", "next_review_at"]),
            models.Index(fields=["user", "skill"]),
            models.Index(fields=["next_review_at"]),
        ]
        constraints = [
            # One mistake row per (user, question). Repeats UPDATE the row.
            models.UniqueConstraint(
                fields=["user", "question"],
                name="learning_core_unique_user_question_mistake",
            ),
        ]
        verbose_name = _("Student mistake")
        verbose_name_plural = _("Student mistakes")

    def __str__(self):
        flag = "✓" if self.mastered else "✗"
        return f"Mistake<{self.user_id}> q={self.question_id} {flag} reviews={self.review_count}"


class MasteryEvent(models.Model):
    """Idempotency lock for mastery processing of ChallengeAnswers.

    `mastery_service.process_challenge_answer(answer)` creates a row
    here keyed by `challenge_answer` BEFORE doing any work. A second
    call for the same answer hits the UNIQUE constraint and returns
    early — so refresh, duplicate POST, or session re-entry can NEVER
    double-update SkillMastery.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mastery_events",
    )
    challenge_answer = models.OneToOneField(
        "courses.ChallengeAnswer",
        on_delete=models.CASCADE,
        related_name="mastery_event",
    )
    processed_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-processed_at"]
        indexes = [
            models.Index(fields=["user", "-processed_at"]),
        ]
        verbose_name = _("Mastery event")
        verbose_name_plural = _("Mastery events")

    def __str__(self):
        return f"MasteryEvent<{self.user_id}> answer={self.challenge_answer_id}"
