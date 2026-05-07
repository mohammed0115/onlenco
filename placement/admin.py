from django.contrib import admin
from .models import PlacementResult


@admin.register(PlacementResult)
class PlacementResultAdmin(admin.ModelAdmin):
    list_display = ("user", "level", "written_score", "speaking_score", "created_at")
    list_filter = ("level",)
    search_fields = ("user__email", "user__username", "feedback")
    readonly_fields = ("created_at",)
