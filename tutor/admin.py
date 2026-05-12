from django.contrib import admin

from .models import AITutorPrompt, TutorConversation, TutorMessage


class TutorMessageInline(admin.TabularInline):
    model = TutorMessage
    extra = 0
    readonly_fields = ("role", "content", "created_at")


@admin.register(TutorConversation)
class TutorConversationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "topic", "updated_at")
    search_fields = ("user__email", "title", "topic")
    list_filter = ("topic",)
    inlines = [TutorMessageInline]


@admin.register(TutorMessage)
class TutorMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("conversation__title", "content", "conversation__user__email")


@admin.register(AITutorPrompt)
class AITutorPromptAdmin(admin.ModelAdmin):
    list_display = ("id", "cefr_level", "lesson_slug", "correction_strategy",
                    "order", "is_active")
    list_filter = ("cefr_level", "correction_strategy", "is_active")
    search_fields = ("lesson_slug", "prompt_en", "prompt_ar")
    list_editable = ("order", "is_active")
    ordering = ("cefr_level", "lesson_slug", "order")

