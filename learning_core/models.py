from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

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
    """A teachable skill (e.g. Grammar at B1, Listening at A2)."""

    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=SKILL_CATEGORY_CHOICES)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "cefr_level", "name"]
        indexes = [
            models.Index(fields=["category", "cefr_level"]),
            models.Index(fields=["is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "category", "cefr_level"],
                name="unique_skill_name_category_level",
            )
        ]

    def __str__(self):
        return f"{self.get_category_display()} · {self.name}"


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

    def __str__(self):
        return f"LearningProfile<{self.user_id}> θ={self.theta_score:.2f}"


class SkillMastery(models.Model):
    """Per-(user, skill) mastery tracking."""

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
    attempts_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    last_practiced_at = models.DateTimeField(null=True, blank=True)
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
        ]

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
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES)
    question = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField()
    explanation = models.TextField(blank=True)
    generated_by_ai = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["cefr_level"]),
            models.Index(fields=["question_type"]),
            models.Index(fields=["difficulty_score"]),
            models.Index(fields=["generated_by_ai"]),
        ]

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

    def __str__(self):
        return f"Rec<{self.user_id}> {self.recommendation_type} p={self.priority:.1f}"


class WeeklyAssessment(models.Model):
    """A periodic assessment triggered every N completed lessons.

    The score is the percentage correct across the bundled exercises. On
    completion, theta + weaknesses + recommendations are refreshed.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="weekly_assessments",
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
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return f"WeeklyAsmt<{self.user_id}> {self.status} score={self.score:.0f}"
