from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import CEFR_CHOICES
from courses.models import GeneratedMediaReviewMixin
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


# Copyright provenance for a Book — the publish gate for the Novel Reader.
# A title only becomes student-facing once it is BOTH copyright-cleared and
# published. Defaults are deliberately conservative (`unknown` + not cleared)
# so nothing leaks before a human confirms the rights.
COPYRIGHT_STATUS_CHOICES = [
    ("unknown",                       _("Unknown / unverified")),
    ("public_domain",                 _("Public domain")),
    ("licensed",                      _("Licensed")),
    ("adapted_original",              _("Adapted / original Onlenco content")),
    ("school_excerpt_with_permission", _("School excerpt with permission")),
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
    code = models.CharField(
        max_length=50, unique=True, blank=True, db_index=True,
        verbose_name=_("Auto code"),
    )

    # --- Copyright / provenance (Novel Reader MVP) ---------------------
    # Additive; existing books default to unknown + not-cleared so nothing
    # is treated as student-facing novel content until a human verifies it.
    copyright_status = models.CharField(
        max_length=32, choices=COPYRIGHT_STATUS_CHOICES, default="unknown",
        db_index=True, verbose_name=_("Copyright status"),
    )
    source_title = models.CharField(
        max_length=200, blank=True, verbose_name=_("Source title"),
        help_text=_("Original work title, e.g. 'The Black Tulip' (Project Gutenberg)."),
    )
    source_url = models.URLField(
        blank=True, verbose_name=_("Source URL"),
        help_text=_("Where the source text legitimately comes from."),
    )
    license_notes = models.TextField(
        blank=True, verbose_name=_("License notes"),
        help_text=_("Permission/license details for licensed or excerpt content."),
    )
    is_copyright_cleared = models.BooleanField(
        default=False, db_index=True, verbose_name=_("Copyright cleared"),
        help_text=_("Gate: must be True before this title can be published to students."),
    )
    content_language = models.CharField(
        max_length=8, default="en", verbose_name=_("Content language"),
    )
    target_cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True,
        verbose_name=_("Target CEFR level"),
    )

    # --- School curriculum metadata -----------------------------------
    is_school_curriculum = models.BooleanField(
        default=False, db_index=True, verbose_name=_("School curriculum"),
    )
    school_country = models.CharField(
        max_length=64, blank=True, verbose_name=_("School country"),
        help_text=_("e.g. 'Sudan'."),
    )
    school_stage = models.CharField(
        max_length=64, blank=True, verbose_name=_("School stage"),
        help_text=_("e.g. 'Secondary — Certificate'."),
    )
    curriculum_notes = models.TextField(
        blank=True, verbose_name=_("Curriculum notes"),
    )

    class Meta:
        ordering = ["-published_at", "title"]
        verbose_name = _("Book")
        verbose_name_plural = _("Books")

    def __str__(self):
        return f"{self.title} ({self.level})"

    def save(self, *args, **kwargs):
        if not self.code and self.level:
            from courses.services.code_generator import (
                generate_book_code, next_book_sequence,
            )
            existing = (
                Book.objects.filter(level=self.level)
                .exclude(pk=self.pk)
                .values_list("code", flat=True)
            )
            seq = next_book_sequence(existing)
            self.code = generate_book_code(self.level, seq)
        super().save(*args, **kwargs)

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
    code = models.CharField(
        max_length=60, unique=True, blank=True, db_index=True,
        verbose_name=_("Auto code"),
    )

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = _("Chapter")
        verbose_name_plural = _("Chapters")

    def __str__(self):
        return f"{self.book.title} — Chapter {self.sort_order}: {self.title}"

    def save(self, *args, **kwargs):
        if not self.code and self.book_id and self.book.code:
            from courses.services.code_generator import generate_chapter_code
            self.code = generate_chapter_code(self.book.code, self.sort_order)
        super().save(*args, **kwargs)

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


# ---------------------------------------------------------------------------
# Interactive Novel Reader MVP (Prompt 19.0B) — segment-level structure.
# These are ADDITIVE: Book/Chapter stay exactly as before. A Chapter is the
# "part"; NovelSegment breaks the part into small reader cards so the body is
# no longer a single blob. Reader UI, quizzes, and content land in 19.0C+.
# ---------------------------------------------------------------------------


class NovelSegment(models.Model):
    """One small reader card inside a Chapter (the novel "part").

    Carries the English text, an optional Arabic translation (translation
    toggle), and an optional short Arabic explanation. One illustration and
    a handful of vocabulary highlights hang off each segment.
    """

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="segments",
        verbose_name=_("Chapter"),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))
    title = models.CharField(max_length=200, blank=True, verbose_name=_("Title"))
    text_en = models.TextField(verbose_name=_("English text"))
    text_ar = models.TextField(
        blank=True, verbose_name=_("Arabic translation"),
        help_text=_("Optional Arabic translation shown via the translation toggle."),
    )
    arabic_summary = models.TextField(
        blank=True, verbose_name=_("Arabic summary"),
        help_text=_("Short Arabic explanation shown at the end of the segment."),
    )
    cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True, verbose_name=_("CEFR level"),
    )
    estimated_reading_seconds = models.PositiveIntegerField(
        default=0, verbose_name=_("Estimated reading seconds"),
    )
    estimated_audio_seconds = models.PositiveIntegerField(
        default=0, verbose_name=_("Estimated audio seconds"),
    )
    is_published = models.BooleanField(
        default=False, db_index=True, verbose_name=_("Published"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["chapter", "order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["chapter", "order"], name="unique_novel_segment_chapter_order",
            ),
        ]
        indexes = [models.Index(fields=["chapter", "order"])]
        verbose_name = _("Novel segment")
        verbose_name_plural = _("Novel segments")

    def __str__(self):
        return f"{self.chapter_id} · seg#{self.order}: {self.title or self.text_en[:30]}"


class NovelVocabularyHighlight(models.Model):
    """A tappable vocabulary word/phrase inside a segment.

    Word/phrase is enough for the MVP — character offsets are optional and
    nullable on purpose, because the text may be re-edited and offsets would
    drift. The reader matches by word/phrase, falling back to offsets only
    when they are present and still valid.
    """

    segment = models.ForeignKey(
        NovelSegment, on_delete=models.CASCADE, related_name="vocabulary_highlights",
        verbose_name=_("Segment"),
    )
    word = models.CharField(max_length=120, verbose_name=_("Word"))
    phrase = models.CharField(
        max_length=200, blank=True, verbose_name=_("Phrase"),
        help_text=_("Optional multi-word phrase if the highlight is longer than one word."),
    )
    meaning_ar = models.CharField(max_length=200, verbose_name=_("Arabic meaning"))
    explanation_ar = models.TextField(
        blank=True, verbose_name=_("Arabic explanation"),
    )
    example_sentence = models.TextField(
        blank=True, verbose_name=_("Example sentence"),
    )
    cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True, verbose_name=_("CEFR level"),
    )
    start_offset = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Start offset"),
    )
    end_offset = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("End offset"),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))
    is_active = models.BooleanField(default=True, db_index=True, verbose_name=_("Active"))

    class Meta:
        ordering = ["segment", "order", "id"]
        indexes = [models.Index(fields=["segment", "order"])]
        verbose_name = _("Novel vocabulary highlight")
        verbose_name_plural = _("Novel vocabulary highlights")

    def __str__(self):
        return self.phrase or self.word


class NovelIllustration(GeneratedMediaReviewMixin, models.Model):
    """One illustration for a segment, on the shared media-review lifecycle.

    Reuses ``GeneratedMediaReviewMixin`` so an illustration is shown to
    students ONLY when ``approved`` AND an image file exists — pending /
    failed / rejected images stay hidden behind a placeholder, exactly like
    lesson media. No generation happens in 19.0B (schema/admin only).
    """

    segment = models.ForeignKey(
        NovelSegment, on_delete=models.CASCADE, related_name="illustrations",
        verbose_name=_("Segment"),
    )
    description = models.TextField(
        blank=True, verbose_name=_("Description / prompt"),
        help_text=_("Illustration brief or image-generation prompt. Not shown to students."),
    )
    image = models.ImageField(
        upload_to="library/novel_illustrations/%Y/%m/", blank=True, null=True,
        validators=[validate_image], verbose_name=_("Image"),
    )
    alt_text = models.CharField(
        max_length=200, blank=True, verbose_name=_("Alt text"),
    )
    order = models.PositiveIntegerField(default=0, verbose_name=_("Order"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["segment", "order", "id"]
        indexes = [models.Index(fields=["segment", "order"])]
        verbose_name = _("Novel illustration")
        verbose_name_plural = _("Novel illustrations")

    def __str__(self):
        return f"illustration<{self.pk}> seg={self.segment_id} ({self.generation_status})"

    @property
    def is_student_visible(self) -> bool:
        """Show to students ONLY when approved AND an image file exists."""
        return self.generation_status == "approved" and bool(self.image)


def validate_novel_import_source(f):
    """Reject anything that is not a supported novel source (Phase 19.0I)."""
    import os as _os
    ext = _os.path.splitext(getattr(f, "name", "") or "")[1].lower()
    if ext not in (".pdf", ".txt", ".docx"):
        raise __import__("django.core.exceptions", fromlist=["ValidationError"]).ValidationError(
            _("Only PDF, TXT or DOCX novel sources are allowed.")
        )


class LibraryImportJob(models.Model):
    """A single admin-driven novel import (Phase 19.0I).

    Tracks an uploaded source file through upload → analyze → apply. The
    uploaded source lives under MEDIA_ROOT (never Git) and is never
    student-facing. Only metadata/preview is stored here — not the full raw
    text — to keep rows small.
    """

    FORMAT_CHOICES = [
        ("pdf", _("PDF")),
        ("txt", _("Text")),
        ("docx", _("Word (DOCX)")),
    ]
    STATUS_CHOICES = [
        ("uploaded", _("Uploaded")),
        ("analyzed", _("Analyzed")),
        ("imported", _("Imported")),
        ("failed", _("Failed")),
        ("cancelled", _("Cancelled")),
    ]

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="library_import_jobs",
    )
    original_filename = models.CharField(max_length=255, blank=True)
    source_file = models.FileField(
        upload_to="library/imports/%Y/%m/", blank=True, null=True,
        validators=[validate_novel_import_source],
        help_text=_("Uploaded novel source — never published to students, never in Git."),
    )
    source_format = models.CharField(max_length=8, choices=FORMAT_CHOICES, blank=True)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default="uploaded", db_index=True,
    )

    # Analysis results (filled at the analyze step).
    detected_text_layer = models.BooleanField(null=True, blank=True)
    needs_ocr = models.BooleanField(default=False)
    page_count = models.PositiveIntegerField(default=0)
    word_count = models.PositiveIntegerField(default=0)
    chapter_count = models.PositiveIntegerField(default=0)
    segment_count = models.PositiveIntegerField(default=0)
    warnings = models.JSONField(default=list, blank=True)
    errors = models.JSONField(default=list, blank=True)
    preview = models.JSONField(default=dict, blank=True)  # titles + short segment preview only

    created_book = models.ForeignKey(
        Book, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="import_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "-created_at"])]
        verbose_name = _("Library import job")
        verbose_name_plural = _("Library import jobs")

    def __str__(self):
        return f"importjob<{self.pk}> {self.original_filename!r} ({self.status})"
