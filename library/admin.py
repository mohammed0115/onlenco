from django.contrib import admin

from .models import Book, Chapter


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

