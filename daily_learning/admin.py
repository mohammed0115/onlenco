from django.contrib import admin

from .models import (
    DailyGoal,
    DailyLearningItem,
    DailyLearningPlan,
    DailyLearningResult,
)


class DailyLearningItemInline(admin.TabularInline):
    model = DailyLearningItem
    extra = 0
    fields = ("order", "item_type", "title", "skill", "cefr_level",
              "difficulty_score", "is_completed")
    readonly_fields = ("completed_at",)
    show_change_link = True


@admin.register(DailyLearningPlan)
class DailyLearningPlanAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "date", "cefr_level", "plan_type",
                    "status", "estimated_minutes", "item_count",
                    "progress_percent", "created_at")
    list_filter = ("status", "plan_type", "cefr_level", "date")
    search_fields = ("user__email", "user__username", "title")
    date_hierarchy = "date"
    inlines = [DailyLearningItemInline]
    readonly_fields = ("created_at", "completed_at", "metadata")
    ordering = ("-date",)

    def item_count(self, obj):
        return obj.items.count()

    def progress_percent(self, obj):
        return f"{obj.progress_percent}%"


@admin.register(DailyLearningItem)
class DailyLearningItemAdmin(admin.ModelAdmin):
    list_display = ("id", "daily_plan", "order", "item_type", "skill",
                    "cefr_level", "has_media", "is_completed")
    list_filter = ("item_type", "skill", "cefr_level", "is_completed")
    search_fields = ("title", "question", "daily_plan__user__email")
    readonly_fields = ("completed_at", "metadata")

    @admin.display(boolean=True, description="Media")
    def has_media(self, obj):
        return bool(obj.image_url or obj.audio_url)


@admin.register(DailyGoal)
class DailyGoalAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "date", "goal_type", "current_value",
                    "target_value", "completed", "reward_xp")
    list_filter = ("goal_type", "completed", "date")
    search_fields = ("user__email", "user__username")
    date_hierarchy = "date"


@admin.register(DailyLearningResult)
class DailyLearningResultAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "daily_plan", "completed_items_count",
                    "total_items_count", "score", "xp_earned",
                    "streak_updated", "created_at")
    list_filter = ("streak_updated",)
    search_fields = ("user__email", "user__username")
    readonly_fields = ("created_at", "weaknesses_improved")
