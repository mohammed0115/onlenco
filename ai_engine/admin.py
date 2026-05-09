from django.contrib import admin

from .models import ModelPredictionLog, ProviderKillSwitch


@admin.register(ModelPredictionLog)
class ModelPredictionLogAdmin(admin.ModelAdmin):
    list_display = ("id", "task_type", "provider", "confidence",
                    "fallback_used", "success", "latency_ms",
                    "user", "created_at")
    list_filter = ("task_type", "provider", "success", "fallback_used")
    search_fields = ("model_version", "error_message", "reason",
                     "user__email", "user__username")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user",)


@admin.register(ProviderKillSwitch)
class ProviderKillSwitchAdmin(admin.ModelAdmin):
    list_display = ("task_type", "provider", "disabled",
                    "reason", "expires_at", "updated_at")
    list_filter = ("task_type", "provider", "disabled")
    search_fields = ("reason",)
    readonly_fields = ("created_at", "updated_at")
