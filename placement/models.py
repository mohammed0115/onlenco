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
        max_length=80, unique=True, db_index=True, blank=True,
        help_text=_(
            "Auto-generated stable identifier (e.g. wr.intro.001). "
            "Leave blank — the system assigns the next free sequence "
            "from the question_type + topic on save."
        ),
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
    # Cached AI "Other possible answers" for ORAL questions (guidance only,
    # never used to grade). Populated once then reused to avoid API cost.
    ai_alternatives = models.JSONField(
        default=list, blank=True,
        help_text=_("Cached alternative answer suggestions (oral guidance)."),
    )
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

    def save(self, *args, **kwargs):
        if not self.code:
            from placement.services.code_generator import (
                code_prefix, generate_question_code,
                next_question_sequence, topic_slug,
            )
            prefix = code_prefix(self.question_type)
            slug = topic_slug(self.topic)
            existing = PlacementQuestion.objects.values_list("code", flat=True)
            seq = next_question_sequence(existing, prefix, slug)
            self.code = generate_question_code(self.question_type, slug, seq)
        super().save(*args, **kwargs)

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
    # How many FAILED speaking call attempts (student attempted but answered
    # < min) — drives the "unable after retries" conservative finalisation.
    speaking_retry_count = models.PositiveSmallIntegerField(default=0)
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


class PlacementSpeakingAttempt(models.Model):
    """One lifetime placement SPEAKING attempt per student (Prompt 16.6F).

    The written part can be retaken, but the live speaking call is a
    one-shot: a student gets exactly ONE *valid* attempt. A re-attempt is
    only possible after an audited admin reset (``reset_by`` / ``reset_at``
    / ``reset_reason`` are stamped on the blocking row; nothing is deleted).

    ``is_used_attempt`` is the gate: a row only "uses up" the lifetime
    attempt when the student actually answered at least one question. A
    connection that dropped before any answer is ``failed_start`` and does
    NOT consume the attempt, so the student can simply try again.
    """

    STATUS_STARTED = "started"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED_START = "failed_start"
    STATUS_INSUFFICIENT = "insufficient_answers"
    STATUS_NEEDS_RETRY = "needs_retry"
    STATUS_UNABLE = "unable_to_answer_after_retries"
    STATUS_FAILED_SYSTEM = "failed_system"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_STARTED, _("Started")),
        (STATUS_COMPLETED, _("Completed")),
        (STATUS_FAILED_START, _("Failed start — no answers")),
        (STATUS_INSUFFICIENT, _("Insufficient answers")),
        (STATUS_NEEDS_RETRY, _("Needs retry — too short")),
        (STATUS_UNABLE, _("Unable to answer after retries")),
        (STATUS_FAILED_SYSTEM, _("Failed — system/STT error")),
        (STATUS_CANCELLED, _("Cancelled")),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="placement_speaking_attempts",
        verbose_name=_("Student"),
    )
    placement_attempt = models.ForeignKey(
        PlacementAttempt, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="speaking_attempts",
    )
    conversation = models.ForeignKey(
        "tutor.TutorConversation", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="placement_speaking_attempts",
    )
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES, default=STATUS_STARTED,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    question_count_answered = models.PositiveSmallIntegerField(default=0)
    duration_seconds = models.PositiveIntegerField(default=0)
    # The gate: True once the student has answered >= 1 question. Only a
    # used attempt blocks future attempts (until an admin reset).
    is_used_attempt = models.BooleanField(default=False, db_index=True)
    # Admin reset audit — set when an admin reopens the test. The presence
    # of ``reset_at`` clears this row from the blocking set.
    reset_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="placement_speaking_resets",
    )
    reset_at = models.DateTimeField(null=True, blank=True)
    reset_reason = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = _("Placement speaking attempt")
        verbose_name_plural = _("Placement speaking attempts")
        indexes = [
            models.Index(fields=["student", "-started_at"]),
            models.Index(fields=["student", "is_used_attempt", "reset_at"]),
        ]

    def __str__(self):
        return (f"SpeakingAttempt<{self.id}> user={self.student_id} "
                f"{self.status} used={self.is_used_attempt}")
