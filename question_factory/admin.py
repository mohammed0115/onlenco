from django.contrib import admin

from .models import (
    GeneratedQuestion,
    GenerationBatch,
    QuestionBlueprint,
    QuestionSeed,
    QuestionVariableSet,
    UserSeedHistory,
)


@admin.register(QuestionBlueprint)
class QuestionBlueprintAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "cefr_level", "skill", "question_type",
                    "generation_strategy", "is_active")
    list_filter = ("cefr_level", "skill", "question_type",
                   "generation_strategy", "is_active")
    search_fields = ("code", "title", "template_pattern")
    raw_id_fields = ("grammar_topic",)


@admin.register(QuestionVariableSet)
class QuestionVariableSetAdmin(admin.ModelAdmin):
    list_display = ("id", "blueprint", "cefr_level", "skill",
                    "difficulty_score", "is_active")
    list_filter = ("cefr_level", "skill", "is_active")
    raw_id_fields = ("blueprint", "grammar_topic")


@admin.register(GeneratedQuestion)
class GeneratedQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "cefr_level", "skill", "question_type",
                    "quality_score", "generated_by", "is_active",
                    "is_reviewed", "approved_for_training")
    list_filter = ("cefr_level", "skill", "question_type", "generated_by",
                   "is_active", "is_reviewed", "approved_for_training")
    search_fields = ("code", "question_text", "correct_answer")
    raw_id_fields = ("blueprint", "grammar_topic")
    readonly_fields = ("content_hash", "created_at", "updated_at")
    actions = ["mark_reviewed", "approve_for_training", "deactivate"]

    @admin.action(description="Mark selected as reviewed")
    def mark_reviewed(self, request, queryset):
        n = queryset.update(is_reviewed=True)
        self.message_user(request, f"{n} item(s) marked reviewed.")

    @admin.action(description="Approve for training")
    def approve_for_training(self, request, queryset):
        n = queryset.update(approved_for_training=True, is_reviewed=True)
        self.message_user(request, f"{n} item(s) approved for training.")

    @admin.action(description="Deactivate")
    def deactivate(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f"{n} item(s) deactivated.")


@admin.register(QuestionSeed)
class QuestionSeedAdmin(admin.ModelAdmin):
    list_display = ("seed_key", "blueprint", "cefr_level", "skill",
                    "difficulty_score", "generated_count", "last_used_at")
    list_filter = ("cefr_level", "skill")
    search_fields = ("seed_key", "content_hash")
    raw_id_fields = ("blueprint", "grammar_topic")
    readonly_fields = ("content_hash", "generated_count",
                       "last_used_at", "created_at")


@admin.register(UserSeedHistory)
class UserSeedHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "seed", "answered", "is_correct", "seen_at")
    list_filter = ("answered", "is_correct")
    raw_id_fields = ("user", "seed")
    readonly_fields = ("content_hash", "seen_at")


@admin.register(GenerationBatch)
class GenerationBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_id", "status", "strategy", "cefr_level", "skill",
                    "accepted_count", "target_count", "duplicate_count",
                    "started_at", "completed_at")
    list_filter = ("status", "strategy", "cefr_level", "skill")
    search_fields = ("batch_id",)
    readonly_fields = ("started_at", "completed_at")
