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

