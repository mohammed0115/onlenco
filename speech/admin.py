from django.contrib import admin

from .models import SpeakingAttempt


@admin.register(SpeakingAttempt)
class SpeakingAttemptAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "source", "duration_seconds",
                    "confidence")
    list_filter = ("source",)
    search_fields = ("transcript", "user__username", "user__email")
    raw_id_fields = ("user",)
    readonly_fields = ("user", "audio_file", "transcript",
                       "duration_seconds", "confidence", "source", "created_at")

    def has_add_permission(self, request):
        return False
