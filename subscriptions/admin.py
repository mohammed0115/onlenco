from django.contrib import admin

from .models import (
    AvatarProfile,
    FreeTrialUsage,
    AITutorSession,
    SubscriptionPlan,
    UserAIPreference,
    UserDailyQuota,
    UserSubscription,
    VoiceProfile,
)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name_en", "ai_tutor_daily_minutes",
        "library_audio_daily_minutes", "price_sdg",
        "is_active", "is_free_trial", "sort_order",
    )
    list_filter = ("is_active", "is_free_trial", "billing_cycle")
    search_fields = ("code", "name_en", "name_ar")
    ordering = ("sort_order", "ai_tutor_daily_minutes")


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "plan", "status", "start_date", "end_date", "auto_renew")
    list_filter = ("status", "plan", "auto_renew")
    search_fields = ("user__email", "user__username", "plan__code")
    raw_id_fields = ("user", "payment")


@admin.register(UserDailyQuota)
class UserDailyQuotaAdmin(admin.ModelAdmin):
    list_display = ("user", "date", "ai_tutor_seconds_used", "library_seconds_used")
    list_filter = ("date",)
    search_fields = ("user__email", "user__username")
    raw_id_fields = ("user",)
    date_hierarchy = "date"


@admin.register(VoiceProfile)
class VoiceProfileAdmin(admin.ModelAdmin):
    list_display = ("code", "name_en", "provider_voice_id", "voice_type", "style", "accent", "tone", "is_active", "sort_order")
    list_filter = ("is_active", "voice_type", "style", "accent", "tone")
    search_fields = ("code", "name_en", "name_ar", "provider_voice_id")
    ordering = ("sort_order",)


@admin.register(AvatarProfile)
class AvatarProfileAdmin(admin.ModelAdmin):
    list_display = ("code", "name_en", "gender", "style", "is_active", "sort_order")
    list_filter = ("is_active", "gender", "style")
    search_fields = ("code", "name_en", "name_ar")
    ordering = ("sort_order",)


@admin.register(UserAIPreference)
class UserAIPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "voice_profile", "avatar_profile", "speed", "pitch", "sound_effects_enabled")
    list_filter = ("speed", "pitch", "sound_effects_enabled")
    raw_id_fields = ("user", "voice_profile", "avatar_profile")
    search_fields = ("user__email", "user__username")


@admin.register(FreeTrialUsage)
class FreeTrialUsageAdmin(admin.ModelAdmin):
    list_display = ("user", "free_seconds_granted", "free_seconds_used", "is_consumed", "granted_at")
    list_filter = ("is_consumed",)
    raw_id_fields = ("user",)
    search_fields = ("user__email", "user__username")


@admin.register(AITutorSession)
class AITutorSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "started_at", "ended_at", "duration_seconds", "status", "quota_source", "voice_profile")
    list_filter = ("status", "source", "quota_source")
    raw_id_fields = ("user", "voice_profile", "avatar_profile")
    search_fields = ("user__email", "user__username")
    date_hierarchy = "started_at"
