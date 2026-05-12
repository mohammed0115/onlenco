from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import CEFR_CHOICES
from courses.validators import (
    validate_audio, validate_document, validate_image, validate_video_url,
)


CATEGORY_CHOICES = [
    ("novel",   _("Novel")),
    ("short",   _("Short story")),
    ("grammar", _("Grammar reference")),
    ("article", _("Article")),
    ("video",   _("Long video")),
]


class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=120, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    level = models.CharField(max_length=2, choices=CEFR_CHOICES)
    summary = models.TextField(blank=True)
    cover = models.ImageField(
        upload_to="library/covers/", blank=True, null=True,
        validators=[validate_image],
    )
    pdf = models.FileField(
        upload_to="library/pdfs/", blank=True, null=True,
        validators=[validate_document],
    )
    video_url = models.URLField(blank=True)
    published_at = models.DateField(blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at", "title"]
        verbose_name = _("Book")
        verbose_name_plural = _("Books")

    def __str__(self):
        return f"{self.title} ({self.level})"

    def clean(self):
        super().clean()
        if self.video_url:
            validate_video_url(self.video_url)


class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="chapters")
    title = models.CharField(max_length=200)
    body = models.TextField()
    # Optional audio for this chapter so it can also serve as a
    # standalone listening unit (A0 audio lessons live here). Upload
    # `audio_file` for a self-hosted recording, or set `audio_url` to
    # point at a CDN / external host. Either renders an `<audio>`
    # element on the chapter page.
    audio_file = models.FileField(
        upload_to="library/audio/%Y/%m/", blank=True, null=True,
        validators=[validate_audio],
        verbose_name=_("Audio file"),
        help_text=_("Upload an audio file (mp3, m4a, webm). Plays before the text."),
    )
    audio_url = models.URLField(
        blank=True,
        verbose_name=_("Audio URL"),
        help_text=_("Optional hosted audio URL — used only when no file is uploaded."),
    )
    duration_seconds = models.PositiveIntegerField(
        default=0, verbose_name=_("Audio duration (seconds)"),
        help_text=_("Approximate audio length for filtering / listing."),
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = _("Chapter")
        verbose_name_plural = _("Chapters")

    def __str__(self):
        return f"{self.book.title} — Chapter {self.sort_order}: {self.title}"

    @property
    def has_audio(self) -> bool:
        return bool(self.audio_file or self.audio_url)

    def get_audio_src(self) -> str:
        """Resolve the audio source to play. File wins over URL."""
        if self.audio_file:
            try:
                return self.audio_file.url
            except Exception:
                pass
        return self.audio_url or ""


class VocabularyExtract(models.Model):
    """A vocabulary word/phrase pulled from a chapter for study."""

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="vocabulary"
    )
    term = models.CharField(max_length=120)
    translation = models.CharField(max_length=200, blank=True)
    pos = models.CharField(max_length=20, blank=True)
    example = models.TextField(blank=True)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    source = models.CharField(max_length=20, default="ai")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chapter", "term"]
        constraints = [
            models.UniqueConstraint(
                fields=["chapter", "term"], name="unique_chapter_term"
            )
        ]
        verbose_name = _("Vocabulary extract")
        verbose_name_plural = _("Vocabulary extracts")

    def __str__(self):
        return self.term


class GrammarExtract(models.Model):
    """A grammar focus topic pulled from a chapter."""

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="grammar_focus"
    )
    topic = models.CharField(max_length=120)
    explanation = models.TextField(blank=True)
    example = models.TextField(blank=True)
    cefr_level = models.CharField(max_length=2, choices=CEFR_CHOICES, blank=True)
    source = models.CharField(max_length=20, default="ai")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chapter", "topic"]
        verbose_name = _("Grammar extract")
        verbose_name_plural = _("Grammar extracts")

    def __str__(self):
        return f"{self.topic} ({self.chapter})"


class ComprehensionQuestion(models.Model):
    """A short-answer or multiple-choice comprehension question."""

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="comprehension_questions"
    )
    question = models.TextField()
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    source = models.CharField(max_length=20, default="ai")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["chapter", "sort_order", "id"]
        verbose_name = _("Comprehension question")
        verbose_name_plural = _("Comprehension questions")

    def __str__(self):
        return f"Q on {self.chapter}: {self.question[:40]}"


class LibraryProgress(models.Model):
    """Tracks a user's progress inside a Book/Chapter."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library_progress",
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="user_progress"
    )
    completed = models.BooleanField(default=False)
    comprehension_score = models.PositiveSmallIntegerField(null=True, blank=True)
    last_position = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "chapter"], name="unique_user_chapter_progress"
            )
        ]
        indexes = [models.Index(fields=["user", "completed"])]
        verbose_name = _("Library progress")
        verbose_name_plural = _("Library progress")

    def __str__(self):
        return f"LibProg<{self.user_id}> ch={self.chapter_id} done={self.completed}"
