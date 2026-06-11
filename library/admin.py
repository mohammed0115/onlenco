from django.contrib import admin
from django.db.models import Count

from .models import (
    Book,
    Chapter,
    ComprehensionQuestion,
    GrammarExtract,
    LibraryProgress,
    NovelIllustration,
    NovelSegment,
    NovelVocabularyHighlight,
    VocabularyExtract,
)


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0
    fields = ("sort_order", "title", "body")
    ordering = ("sort_order", "id")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = (
        "title", "author", "category", "level",
        "copyright_status", "is_copyright_cleared",
        "is_school_curriculum", "school_country", "target_cefr_level",
        "is_published", "published_at",
    )
    list_filter = (
        "category", "level", "is_published",
        "copyright_status", "is_copyright_cleared",
        "is_school_curriculum", "school_country", "target_cefr_level",
    )
    search_fields = ("title", "author", "summary", "source_title")
    inlines = [ChapterInline]
    fieldsets = (
        (None, {
            "fields": ("title", "author", "category", "level", "summary",
                       "cover", "pdf", "video_url", "published_at", "is_published", "code"),
        }),
        ("Copyright / provenance", {
            "fields": ("copyright_status", "is_copyright_cleared",
                       "source_title", "source_url", "license_notes",
                       "content_language", "target_cefr_level"),
            "description": (
                "A title must be copyright-cleared AND published before it is "
                "shown to students as novel content."
            ),
        }),
        ("School curriculum", {
            "fields": ("is_school_curriculum", "school_country",
                       "school_stage", "curriculum_notes"),
        }),
    )


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("book", "sort_order", "title", "has_audio_indicator",
                    "segment_count", "duration_seconds")
    list_filter = ("book__level", "book__category")
    search_fields = ("book__title", "title", "body")
    fields = (
        "book", "sort_order", "title", "body",
        "audio_file", "audio_url", "duration_seconds",
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_segment_count=Count("segments"))

    @admin.display(boolean=True, description="Audio")
    def has_audio_indicator(self, obj):
        return obj.has_audio

    @admin.display(description="Segments", ordering="_segment_count")
    def segment_count(self, obj):
        return obj._segment_count


@admin.register(VocabularyExtract)
class VocabularyExtractAdmin(admin.ModelAdmin):
    list_display = ("term", "translation", "chapter", "cefr_level", "source")
    list_filter = ("cefr_level", "source")
    search_fields = ("term", "translation", "chapter__title", "chapter__book__title")


@admin.register(GrammarExtract)
class GrammarExtractAdmin(admin.ModelAdmin):
    list_display = ("topic", "chapter", "cefr_level", "source")
    list_filter = ("cefr_level", "source")
    search_fields = ("topic", "explanation", "chapter__title")


@admin.register(ComprehensionQuestion)
class ComprehensionQuestionAdmin(admin.ModelAdmin):
    list_display = ("chapter", "sort_order", "question_short")
    list_filter = ("source",)
    search_fields = ("question", "correct_answer", "chapter__title")

    def question_short(self, obj):
        return (obj.question[:60] + "…") if len(obj.question) > 60 else obj.question


@admin.register(LibraryProgress)
class LibraryProgressAdmin(admin.ModelAdmin):
    list_display = ("user", "chapter", "completed", "comprehension_score", "updated_at")
    list_filter = ("completed",)
    search_fields = ("user__username", "chapter__book__title")


# ---------------------------------------------------------------------------
# Interactive Novel Reader MVP (19.0B)
# ---------------------------------------------------------------------------


class NovelVocabularyHighlightInline(admin.TabularInline):
    model = NovelVocabularyHighlight
    extra = 0
    fields = ("order", "word", "phrase", "meaning_ar", "cefr_level", "is_active")
    ordering = ("order", "id")


class NovelIllustrationInline(admin.TabularInline):
    model = NovelIllustration
    extra = 0
    fields = ("order", "image", "alt_text", "generation_status")
    ordering = ("order", "id")


@admin.register(NovelSegment)
class NovelSegmentAdmin(admin.ModelAdmin):
    list_display = ("chapter", "order", "title", "cefr_level", "is_published")
    list_filter = ("is_published", "cefr_level", "chapter__book")
    search_fields = ("title", "text_en", "text_ar", "chapter__book__title")
    ordering = ("chapter", "order")
    inlines = [NovelVocabularyHighlightInline, NovelIllustrationInline]


@admin.register(NovelVocabularyHighlight)
class NovelVocabularyHighlightAdmin(admin.ModelAdmin):
    list_display = ("segment", "word", "phrase", "meaning_ar", "cefr_level", "is_active")
    list_filter = ("is_active", "cefr_level")
    search_fields = ("word", "phrase", "meaning_ar", "segment__chapter__book__title")
    ordering = ("segment", "order")


@admin.register(NovelIllustration)
class NovelIllustrationAdmin(admin.ModelAdmin):
    list_display = ("segment", "order", "generation_status", "is_student_visible_display")
    list_filter = ("generation_status",)
    search_fields = ("alt_text", "description", "segment__chapter__book__title")
    ordering = ("segment", "order")

    @admin.display(boolean=True, description="Student visible")
    def is_student_visible_display(self, obj):
        return obj.is_student_visible

