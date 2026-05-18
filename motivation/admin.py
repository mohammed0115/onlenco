from django.contrib import admin

from .models import (
    Achievement,
    GameEventSound,
    LearnerActivitySnapshot,
    MotivationMessage,
    MotivationPreference,
    UserAchievement,
    UserBadge,
    UserXP,
)


@admin.register(GameEventSound)
class GameEventSoundAdmin(admin.ModelAdmin):
    list_display = ("code", "is_active", "animation", "audio_url", "updated_at")
    list_filter = ("is_active", "animation")
    search_fields = ("code", "message_en", "message_ar")


@admin.register(LearnerActivitySnapshot)
class LearnerActivitySnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "user", "date", "lessons_completed", "questions_answered",
        "quiz_accuracy", "ai_chat_minutes", "current_streak_days",
        "cefr_level",
    )
    list_filter = ("date", "cefr_level")
    search_fields = ("user__email", "user__username")
    date_hierarchy = "date"


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("code", "category", "threshold_value", "xp_reward", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name", "description")


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "achievement", "earned_at")
    list_filter = ("achievement__category",)
    search_fields = ("user__email", "user__username", "achievement__code")
    readonly_fields = ("earned_at",)


@admin.register(UserXP)
class UserXPAdmin(admin.ModelAdmin):
    list_display = ("user", "level_number", "total_xp", "weekly_xp", "monthly_xp", "updated_at")
    search_fields = ("user__email", "user__username")


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ("user", "badge_code", "badge_name", "earned_at")
    search_fields = ("user__email", "user__username", "badge_code")


@admin.register(MotivationMessage)
class MotivationMessageAdmin(admin.ModelAdmin):
    list_display = (
        "user", "message_type", "tone", "language", "status",
        "sent_via", "created_at",
    )
    list_filter = ("message_type", "status", "tone", "language")
    search_fields = ("user__email", "title", "message")
    date_hierarchy = "created_at"


@admin.register(MotivationPreference)
class MotivationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user", "preferred_tone", "motivation_frequency",
        "enable_motivation_notifications", "enable_email_motivation",
    )
    list_filter = ("preferred_tone", "motivation_frequency",
                   "enable_motivation_notifications", "enable_email_motivation")
    search_fields = ("user__email", "user__username")
