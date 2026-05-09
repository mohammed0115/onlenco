from django.contrib import admin

from .models import (
    DatasetExportJob,
    QuestionTemplate,
    SubstitutionBank,
    Topic,
    TrainingDataset,
)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "kind", "cefr_level", "parent", "is_active")
    list_filter = ("kind", "cefr_level", "is_active")
    search_fields = ("name", "slug")
    raw_id_fields = ("parent",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(SubstitutionBank)
class SubstitutionBankAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "size", "is_active", "updated_at")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "kind")


@admin.register(QuestionTemplate)
class QuestionTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "topic", "question_type", "cefr_level",
                    "distractor_strategy", "is_active", "version")
    list_filter = ("question_type", "cefr_level", "distractor_strategy", "is_active")
    search_fields = ("code", "name", "pattern")
    raw_id_fields = ("topic",)


@admin.register(TrainingDataset)
class TrainingDatasetAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "status", "row_count", "last_exported_at")
    list_filter = ("kind", "status")
    search_fields = ("name",)
    raw_id_fields = ("created_by",)
    readonly_fields = ("row_count", "last_export_path", "last_exported_at")


@admin.register(DatasetExportJob)
class DatasetExportJobAdmin(admin.ModelAdmin):
    list_display = ("id", "dataset", "status", "row_count", "bytes_written",
                    "started_at", "completed_at")
    list_filter = ("status",)
    raw_id_fields = ("dataset",)
    readonly_fields = ("started_at", "completed_at", "row_count", "bytes_written")
