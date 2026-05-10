from django.contrib import admin

from .models import (
    PlacementAttempt, PlacementAttemptQuestion, PlacementQuestion,
    PlacementResult,
)


@admin.register(PlacementResult)
class PlacementResultAdmin(admin.ModelAdmin):
    list_display = (
        "user", "level", "overall_score", "written_score", "speaking_score",
        "grammar_score", "vocabulary_score", "created_at",
    )
    list_filter = ("level",)
    search_fields = ("user__email", "user__username", "feedback")
    readonly_fields = ("created_at",)


@admin.register(PlacementQuestion)
class PlacementQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "code", "question_type", "skill", "topic",
        "cefr_min_level", "cefr_max_level", "difficulty_score", "is_active",
    )
    list_filter = (
        "question_type", "skill", "topic", "cefr_min_level",
        "cefr_max_level", "is_active",
    )
    search_fields = ("code", "question_text", "question_text_ar")
    list_editable = ("is_active",)
    fieldsets = (
        (None, {
            "fields": ("code", "is_active", "question_type", "skill", "topic"),
        }),
        ("Content", {
            "fields": ("question_text", "question_text_ar", "options",
                       "expected_answer_type", "scoring_rubric"),
        }),
        ("Targeting", {
            "fields": ("cefr_min_level", "cefr_max_level", "difficulty_score"),
        }),
        ("Audit", {
            "classes": ("collapse",),
            "fields": ("created_at", "updated_at"),
        }),
    )
    readonly_fields = ("created_at", "updated_at")


class PlacementAttemptQuestionInline(admin.TabularInline):
    model = PlacementAttemptQuestion
    extra = 0
    fields = (
        "section", "order", "question", "score", "skill_score",
        "grammar_score", "vocabulary_score", "fluency_score",
        "pronunciation_score", "completed_at", "user_answer_text",
        "transcript",
    )
    readonly_fields = ("section", "order", "question")
    show_change_link = True


@admin.register(PlacementAttempt)
class PlacementAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "status", "recommended_cefr_level",
        "written_score", "speaking_score", "grammar_score",
        "vocabulary_score", "fluency_score", "overall_score", "started_at",
    )
    list_filter = ("status", "recommended_cefr_level")
    search_fields = ("user__email", "user__username")
    raw_id_fields = ("user", "result")
    readonly_fields = ("started_at", "completed_at")
    inlines = [PlacementAttemptQuestionInline]


@admin.register(PlacementAttemptQuestion)
class PlacementAttemptQuestionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "attempt", "section", "order", "question", "score",
        "grammar_score", "vocabulary_score", "fluency_score",
        "pronunciation_score", "completed_at",
    )
    list_filter = ("section",)
    search_fields = ("question__code", "user_answer_text", "transcript")
    raw_id_fields = ("attempt", "question")
