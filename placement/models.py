from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
from accounts.models import CEFR_CHOICES


class PlacementResult(models.Model):
    """Stored result of one AI placement assessment."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="placement_results",
    )
    written_score = models.PositiveSmallIntegerField(null=True, blank=True)
    speaking_score = models.PositiveSmallIntegerField(null=True, blank=True)
    grammar_score = models.PositiveSmallIntegerField(null=True, blank=True)
    vocabulary_score = models.PositiveSmallIntegerField(null=True, blank=True)
    pronunciation_score = models.PositiveSmallIntegerField(null=True, blank=True)
    fluency_score = models.PositiveSmallIntegerField(null=True, blank=True)
    overall_score = models.PositiveSmallIntegerField(null=True, blank=True)
    level = models.CharField(max_length=2, choices=CEFR_CHOICES)
    feedback = models.TextField(blank=True)
    transcript = models.JSONField(default=dict)
    audio = models.FileField(upload_to="placement/audio/%Y/%m/", blank=True, null=True)
    audio_transcript = models.TextField(blank=True)
    audio_duration_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Placement result")
        verbose_name_plural = _("Placement results")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.level} ({self.created_at:%Y-%m-%d})"


# ---------------------------------------------------------------------------
# Question bank — Placement test now pulls 5 written + 5 speaking questions
# at random from this table instead of using hard-coded prompts.
# ---------------------------------------------------------------------------

QUESTION_TYPE_CHOICES = [
    ("written",  _("Written")),
    ("speaking", _("Speaking")),
]
SKILL_CHOICES = [
    ("grammar",       _("Grammar")),
    ("vocabulary",    _("Vocabulary")),
    ("writing",       _("Writing")),
    ("speaking",      _("Speaking")),
    ("fluency",       _("Fluency")),
    ("comprehension", _("Comprehension")),
]
EXPECTED_ANSWER_CHOICES = [
    ("short_text", _("Short text")),
    ("sentence",   _("Sentence")),
    ("paragraph",  _("Paragraph")),
    ("voice",      _("Voice / transcript")),
    ("mcq",        _("Multiple choice")),
]
TOPIC_CHOICES = [
    ("intro",       _("Introduction / personal")),
    ("grammar_fix", _("Grammar fill-blank / correct")),
    ("sentence",    _("Sentence / paragraph")),
    ("daily",       _("Daily routine / past / future")),
    ("reason",      _("Reason / opinion / goal")),
    ("name",        _("Name / introduction")),
    ("age_country", _("Age / country / nationality")),
    ("work_study",  _("Work / study / family")),
    ("hobby",       _("Hobby / free time")),
    ("travel",      _("Travel / opinion")),
]


class PlacementQuestion(models.Model):
    """A single placement-test question, sourced from the bank.

    `code` is a stable identifier (e.g. `wr.intro.001`) so the seeder
    can run idempotently via `update_or_create(code=...)`. Bilingual
    text lives on the row itself — no `gettext_lazy` because the
    catalog is too large to maintain in `.po` files and admins should
    edit copy without touching code.
    """

    code = models.CharField(
        max_length=80, unique=True, db_index=True,
        help_text=_("Stable identifier — used by the seeder for idempotency."),
    )
    question_text = models.TextField(verbose_name=_("Question (English)"))
    question_text_ar = models.TextField(
        blank=True, verbose_name=_("Question (Arabic)"),
        help_text=_("Optional. Falls back to English if blank."),
    )
    question_type = models.CharField(
        max_length=12, choices=QUESTION_TYPE_CHOICES, db_index=True,
        verbose_name=_("Question type"),
    )
    skill = models.CharField(
        max_length=20, choices=SKILL_CHOICES, db_index=True,
        verbose_name=_("Skill"),
    )
    topic = models.CharField(
        max_length=20, choices=TOPIC_CHOICES, blank=True, db_index=True,
        verbose_name=_("Topic bucket"),
    )
    cefr_min_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, default="A0",
        verbose_name=_("CEFR min level"),
    )
    cefr_max_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, default="C2",
        verbose_name=_("CEFR max level"),
    )
    difficulty_score = models.FloatField(
        default=0.5,
        verbose_name=_("Difficulty (0..1)"),
        help_text=_("0 = trivial A0, 1 = C2 advanced."),
    )
    expected_answer_type = models.CharField(
        max_length=12, choices=EXPECTED_ANSWER_CHOICES, default="sentence",
        verbose_name=_("Expected answer type"),
    )
    options = models.JSONField(
        default=list, blank=True,
        verbose_name=_("MCQ options"),
        help_text=_("Used when expected_answer_type='mcq'."),
    )
    scoring_rubric = models.JSONField(
        default=dict, blank=True,
        verbose_name=_("Scoring rubric"),
        help_text=_("Free-form JSON used by the assessor."),
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["question_type", "topic", "code"]
        verbose_name = _("Placement question")
        verbose_name_plural = _("Placement questions")
        indexes = [
            models.Index(fields=["question_type", "is_active"]),
            models.Index(fields=["topic", "is_active"]),
        ]

    def __str__(self):
        return f"[{self.code}] {self.question_text[:60]}"

    def text_for(self, language: str) -> str:
        """Return the question in the requested language with EN fallback."""
        if (language or "").lower().startswith("ar") and self.question_text_ar.strip():
            return self.question_text_ar
        return self.question_text


class PlacementAttempt(models.Model):
    """One full placement run for a user.

    Created when the student clicks 'Take Placement Test'. Holds the
    selected questions (via `PlacementAttemptQuestion`) so refreshing
    the page returns the same 5+5 instead of re-randomising.
    """

    STATUS_CHOICES = [
        ("started",            _("Started")),
        ("written_completed",  _("Written completed")),
        ("speaking_completed", _("Speaking completed")),
        ("completed",          _("Completed")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="placement_attempts",
        verbose_name=_("Student"),
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="started",
    )
    written_score = models.PositiveSmallIntegerField(null=True, blank=True)
    speaking_score = models.PositiveSmallIntegerField(null=True, blank=True)
    grammar_score = models.PositiveSmallIntegerField(null=True, blank=True)
    vocabulary_score = models.PositiveSmallIntegerField(null=True, blank=True)
    fluency_score = models.PositiveSmallIntegerField(null=True, blank=True)
    pronunciation_score = models.PositiveSmallIntegerField(null=True, blank=True)
    overall_score = models.PositiveSmallIntegerField(null=True, blank=True)
    recommended_cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True,
    )
    feedback = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result = models.ForeignKey(
        PlacementResult, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="attempts",
        help_text=_("Linked PlacementResult once scoring completes."),
    )
    voice_conversation = models.ForeignKey(
        "tutor.TutorConversation", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="placement_attempts",
        help_text=_("Linked TutorConversation when the speaking step is "
                    "done via a live voice call (Part 2 of placement)."),
    )

    class Meta:
        ordering = ["-started_at"]
        verbose_name = _("Placement attempt")
        verbose_name_plural = _("Placement attempts")
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"PlacementAttempt<{self.id}> {self.user_id} {self.status}"


class PlacementAttemptQuestion(models.Model):
    """Per-attempt copy of a selected question + the user's answer.

    Decoupled from `PlacementQuestion` so editing or deactivating a bank
    question after-the-fact doesn't corrupt past attempts.
    """

    SECTION_CHOICES = [
        ("written",  _("Written")),
        ("speaking", _("Speaking")),
    ]

    attempt = models.ForeignKey(
        PlacementAttempt, on_delete=models.CASCADE, related_name="questions",
    )
    question = models.ForeignKey(
        PlacementQuestion, on_delete=models.PROTECT,
        related_name="attempt_uses",
        help_text=_("PROTECT — bank questions can't be deleted while still referenced."),
    )
    section = models.CharField(max_length=12, choices=SECTION_CHOICES, db_index=True)
    order = models.PositiveSmallIntegerField(default=0)
    user_answer_text = models.TextField(blank=True)
    transcript = models.TextField(blank=True)
    audio_file = models.FileField(
        upload_to="placement/attempts/%Y/%m/", blank=True, null=True,
    )
    score = models.FloatField(null=True, blank=True)
    skill_score = models.FloatField(null=True, blank=True)
    grammar_score = models.FloatField(null=True, blank=True)
    vocabulary_score = models.FloatField(null=True, blank=True)
    fluency_score = models.FloatField(null=True, blank=True)
    pronunciation_score = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    error_analysis = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["attempt", "section", "order", "id"]
        verbose_name = _("Placement attempt question")
        verbose_name_plural = _("Placement attempt questions")
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_attempt_question",
            ),
        ]
        indexes = [
            models.Index(fields=["attempt", "section", "order"]),
        ]

    def __str__(self):
        return f"AttQ<{self.attempt_id}.{self.order}> {self.question.code}"
