from django.conf import settings
from django.db import models


from django.utils.translation import gettext_lazy as _
class TutorConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="tutor_conversations",
    )
    title = models.CharField(max_length=200, blank=True)
    topic = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Tutor conversation")
        verbose_name_plural = _("Tutor conversations")
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title or f"Conversation #{self.pk}"


class TutorMessage(models.Model):
    ROLE_CHOICES = [("user", "user"), ("assistant", "assistant")]

    conversation = models.ForeignKey(
        TutorConversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Tutor message")
        verbose_name_plural = _("Tutor messages")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:40]}".strip()


CEFR_CHOICES = [
    ("A0", "A0"), ("A1", "A1"), ("A2", "A2"),
    ("B1", "B1"), ("B2", "B2"),
    ("C1", "C1"), ("C2", "C2"),
]


class VoiceCallEvaluation(models.Model):
    """One-shot evaluation of a voice-call session.

    Written at end-of-call by `evaluation_service.evaluate_voice_call`.
    Scores are 0-100; CEFR is derived from overall_score + vocabulary
    range. Heuristic-driven for now (word count, turn count, unique-token
    ratio) — schema is ready for an AI-driven assessor to take over.
    """

    conversation = models.OneToOneField(
        "TutorConversation", on_delete=models.CASCADE, related_name="evaluation",
    )
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    fluency_score = models.PositiveSmallIntegerField(null=True, blank=True)
    vocabulary_score = models.PositiveSmallIntegerField(null=True, blank=True)
    grammar_score = models.PositiveSmallIntegerField(null=True, blank=True)
    pronunciation_score = models.PositiveSmallIntegerField(null=True, blank=True)
    overall_score = models.PositiveSmallIntegerField(null=True, blank=True)
    summary = models.TextField(blank=True)
    word_count = models.PositiveIntegerField(default=0)
    turns_count = models.PositiveSmallIntegerField(default=0)
    seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Voice call evaluation")
        verbose_name_plural = _("Voice call evaluations")

    def __str__(self):
        return f"VoiceCallEvaluation<conv={self.conversation_id} {self.cefr_level or '-'}>"


# ---------------------------------------------------------------------------
# Curriculum-driven tutor prompts
# ---------------------------------------------------------------------------

CORRECTION_STRATEGY_CHOICES = [
    # Repeat the right version warmly. The default for A0/A1.
    ("echo-and-encourage", "Echo and encourage"),
    # Add a mouth/lip hint (used for /p/, /v/, /w/).
    ("mouth-position", "Mouth position hint"),
    # Point at the visual shape of the letter (used for b vs d).
    ("letter-shape", "Letter-shape hint"),
    # Highlight the missing small word (used for missing 'is' or 'a').
    ("add-missing-word", "Add the missing word"),
    # B1+ — explicit Quick-fix line with one-clause WHY.
    ("quick-fix-with-why", "Quick fix with rationale"),
]


class AITutorPrompt(models.Model):
    """Curriculum-anchored AI-tutor scenario.

    A row per (lesson, prompt) — when a learner opens the tutor inside
    a specific lesson, the chat service can pull these to drive the
    initial turn instead of starting a blank-slate conversation.

    Loaded from ``Docs/curriculum/A0/tutor/week_XX.md`` by the
    ``import_a0_curriculum`` management command.
    """

    # Optional FK to a courses-app Lesson. Using a string ref to avoid
    # creating a hard import cycle if `tutor` and `courses` are
    # configured in separate INSTALLED_APPS subsets.
    lesson = models.ForeignKey(
        "courses.Lesson",
        on_delete=models.CASCADE,
        related_name="tutor_prompts",
        null=True, blank=True,
        verbose_name=_("Lesson"),
    )
    # Free-form slug so a prompt can live outside any Lesson (e.g.
    # the placement-flow tutor warmups).
    lesson_slug = models.CharField(
        max_length=120, blank=True, db_index=True,
        verbose_name=_("Lesson slug"),
        help_text=_("Free-form slug; lets a prompt live outside any Lesson row."),
    )
    cefr_level = models.CharField(
        max_length=2, choices=[
            ("A0", "A0"), ("A1", "A1"), ("A2", "A2"),
            ("B1", "B1"), ("B2", "B2"), ("C1", "C1"), ("C2", "C2"),
        ],
        default="A0",
    )
    prompt_en = models.TextField(verbose_name=_("Prompt (EN)"))
    prompt_ar = models.TextField(verbose_name=_("Prompt (AR)"))
    expected_student_answer = models.TextField(
        blank=True,
        help_text=_("Reference answer the chat service can score against."),
    )
    correction_strategy = models.CharField(
        max_length=24, choices=CORRECTION_STRATEGY_CHOICES,
        default="echo-and-encourage",
    )
    difficulty_score = models.FloatField(default=0.1)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["lesson", "order", "id"]
        indexes = [
            models.Index(fields=["lesson_slug", "order"]),
            models.Index(fields=["cefr_level", "is_active"]),
        ]
        verbose_name = _("AI tutor prompt")
        verbose_name_plural = _("AI tutor prompts")

    def __str__(self):
        return f"TutorPrompt<{self.cefr_level}> {self.prompt_en[:40]}"


# ---------------------------------------------------------------------------
# Phase 7 — AI Tutor inside Challenges
# ---------------------------------------------------------------------------

class ChallengeAIInteraction(models.Model):
    """Audit log for every AI call originated from inside a Challenge.

    Used by guardrails to count per-session / per-day calls, and by the
    summary view to surface any AI feedback the student already paid
    tokens for. Never stores raw prompts — only the sanitised
    `prompt_hash` so we can detect repeats without leaking context.
    """

    INTERACTION_TYPE_CHOICES = [
        ("wrong_answer_explanation",  _("Wrong answer explanation")),
        ("speaking_feedback",         _("Speaking feedback")),
        ("roleplay",                  _("Roleplay turn")),
        ("end_advice",                _("End-of-challenge advice")),
        ("mistake_explanation",       _("Mistake explanation")),
        ("conversation_enhancement",  _("Conversation reply suggestion")),
    ]

    STATUS_CHOICES = [
        ("success",  _("Success")),
        ("fallback", _("Fallback")),
        ("failed",   _("Failed")),
        ("skipped",  _("Skipped")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="challenge_ai_interactions",
    )
    session = models.ForeignKey(
        "courses.ChallengeSession", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="ai_interactions",
    )
    question = models.ForeignKey(
        "courses.LessonQuestion", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="ai_interactions",
    )
    challenge_answer = models.ForeignKey(
        "courses.ChallengeAnswer", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="ai_interactions",
    )
    interaction_type = models.CharField(
        max_length=32, choices=INTERACTION_TYPE_CHOICES,
    )
    prompt_hash = models.CharField(max_length=64, blank=True)
    response_en = models.TextField(blank=True)
    response_ar = models.TextField(blank=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="success",
    )
    tokens_used = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=40, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["session", "-created_at"]),
            models.Index(fields=["interaction_type", "-created_at"]),
        ]
        verbose_name = _("Challenge AI interaction")
        verbose_name_plural = _("Challenge AI interactions")

    def __str__(self):
        return f"AIInt<{self.user_id}> {self.interaction_type}/{self.status}"


class AIShortRoleplaySession(models.Model):
    """A short, scoped roleplay tied to a specific Challenge question.

    Capped at `max_turns` (default 5). Once `turns_count` reaches it,
    the runner returns a closing message and refuses further turns.
    """

    STATUS_CHOICES = [
        ("active",    _("Active")),
        ("completed", _("Completed")),
        ("abandoned", _("Abandoned")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="ai_roleplay_sessions",
    )
    challenge_session = models.ForeignKey(
        "courses.ChallengeSession", on_delete=models.CASCADE,
        related_name="ai_roleplay_sessions",
    )
    question = models.ForeignKey(
        "courses.LessonQuestion", on_delete=models.CASCADE,
        related_name="ai_roleplay_sessions",
    )
    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default="active",
    )
    turns_count = models.PositiveIntegerField(default=0)
    max_turns = models.PositiveSmallIntegerField(default=5)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["challenge_session"]),
        ]
        verbose_name = _("AI roleplay session")
        verbose_name_plural = _("AI roleplay sessions")

    def __str__(self):
        return (
            f"Roleplay<{self.user_id}> q={self.question_id} "
            f"{self.turns_count}/{self.max_turns} {self.status}"
        )


class AIShortRoleplayMessage(models.Model):
    """One turn inside a short roleplay."""

    SENDER_CHOICES = [("user", _("User")), ("ai", _("AI"))]

    roleplay_session = models.ForeignKey(
        AIShortRoleplaySession, on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.CharField(max_length=6, choices=SENDER_CHOICES)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("AI roleplay message")
        verbose_name_plural = _("AI roleplay messages")

    def __str__(self):
        return f"{self.sender}: {self.message[:40]}".strip()

