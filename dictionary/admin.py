from django.contrib import admin

from .models import DictionaryEntry


@admin.register(DictionaryEntry)
class DictionaryEntryAdmin(admin.ModelAdmin):
    list_display = ("english", "arabic", "pos", "source", "lookup_count", "created_at")
    list_filter = ("pos", "source")
    search_fields = ("english", "arabic", "example_en", "example_ar", "notes")
    readonly_fields = ("lookup_count", "created_at")

