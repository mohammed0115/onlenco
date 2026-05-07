from django.contrib import admin

from .models import (
    Book,
    Chapter,
    ComprehensionQuestion,
    GrammarExtract,
    LibraryProgress,
    VocabularyExtract,
)


class ChapterInline(admin.TabularInline):
    model = Chapter
    extra = 0
    fields = ("sort_order", "title", "body")
    ordering = ("sort_order", "id")


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "category", "level", "is_published", "published_at")
    list_filter = ("category", "level", "is_published")
    search_fields = ("title", "author", "summary")
    inlines = [ChapterInline]


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("book", "sort_order", "title")
    list_filter = ("book__level", "book__category")
    search_fields = ("book__title", "title", "body")


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

