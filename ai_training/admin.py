from django.contrib import admin

from .models import (
    AITrainingExample, DatasetBuild, DatasetExport, DatasetQualityReport,
)


@admin.register(AITrainingExample)
class AITrainingExampleAdmin(admin.ModelAdmin):
    list_display = ("id", "task_type", "cefr_level", "skill",
                    "quality_score", "split", "is_approved", "created_at")
    list_filter = ("task_type", "cefr_level", "skill",
                   "split", "is_approved", "language")
    search_fields = ("content_hash", "source_type")
    readonly_fields = ("content_hash", "created_at")


@admin.register(DatasetBuild)
class DatasetBuildAdmin(admin.ModelAdmin):
    list_display = ("name", "task_type", "status",
                    "example_count", "rejected_count", "duplicate_count",
                    "started_at", "completed_at")
    list_filter = ("task_type", "status")
    search_fields = ("name",)
    readonly_fields = ("started_at", "completed_at")


@admin.register(DatasetExport)
class DatasetExportAdmin(admin.ModelAdmin):
    list_display = ("id", "build", "format", "split",
                    "row_count", "bytes_written", "status",
                    "started_at", "completed_at")
    list_filter = ("format", "split", "status")
    raw_id_fields = ("build",)
    readonly_fields = ("started_at", "completed_at",
                       "row_count", "bytes_written")


@admin.register(DatasetQualityReport)
class DatasetQualityReportAdmin(admin.ModelAdmin):
    list_display = ("id", "build", "total_examples", "avg_quality_score",
                    "duplicates_removed", "private_data_filtered",
                    "low_quality_filtered")
    raw_id_fields = ("build",)
    readonly_fields = ("created_at",)
