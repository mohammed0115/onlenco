from django.contrib import admin

from .models import (
    AIDailyUsageSummary,
    AIModelPricing,
    AIUsageLog,
    StudentDailyAILimit,
)


@admin.register(AIModelPricing)
class AIModelPricingAdmin(admin.ModelAdmin):
    list_display = (
        "provider", "model_name", "input_price_per_1m_tokens",
        "output_price_per_1m_tokens", "audio_input_price_per_minute",
        "audio_output_price_per_minute", "currency", "is_active",
        "effective_from", "effective_to",
    )
    list_filter = ("provider", "is_active", "currency")
    search_fields = ("model_name",)
    list_editable = ("is_active",)
    ordering = ("provider", "model_name", "-effective_from")


@admin.register(AIUsageLog)
class AIUsageLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at", "usage_date", "role", "feature", "model_name",
        "status", "total_tokens", "ai_minutes_used", "estimated_cost_usd",
        "user",
    )
    list_filter = ("status", "feature", "role", "provider", "model_name", "usage_date")
    search_fields = ("user__username", "request_id", "session_id", "model_name")
    readonly_fields = [f.name for f in AIUsageLog._meta.fields]
    date_hierarchy = "usage_date"

    def has_add_permission(self, request):
        return False


@admin.register(AIDailyUsageSummary)
class AIDailyUsageSummaryAdmin(admin.ModelAdmin):
    list_display = (
        "date", "role", "user", "organization", "total_requests",
        "failed_requests", "total_tokens", "ai_minutes_used",
        "estimated_cost_usd", "content_generation_cost",
    )
    list_filter = ("role", "date", "organization")
    search_fields = ("user__username",)
    date_hierarchy = "date"


@admin.register(StudentDailyAILimit)
class StudentDailyAILimitAdmin(admin.ModelAdmin):
    list_display = (
        "date", "student", "plan_name", "allowed_minutes", "used_minutes",
        "remaining_minutes", "is_free_first_day", "is_exceeded",
    )
    list_filter = ("date", "is_free_first_day", "is_exceeded", "plan_name")
    search_fields = ("student__username",)
    date_hierarchy = "date"
