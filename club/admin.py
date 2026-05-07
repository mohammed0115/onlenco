from django.contrib import admin

from .models import ClubEvent, ClubRSVP


@admin.action(description="Mark all 'going' RSVPs as attended")
def mark_going_attended(modeladmin, request, queryset):
    total = 0
    for event in queryset:
        total += event.rsvps.filter(status="going").update(attended=True)
    modeladmin.message_user(request, f"Marked {total} RSVP(s) as attended.")


@admin.register(ClubEvent)
class ClubEventAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_at", "capacity", "is_published")
    list_filter = ("is_published", "starts_at")
    search_fields = ("title", "topic", "description", "host_name")
    actions = [mark_going_attended]


@admin.register(ClubRSVP)
class ClubRSVPAdmin(admin.ModelAdmin):
    list_display = ("event", "user", "status", "attended", "updated_at")
    list_filter = ("status", "attended")
    search_fields = ("event__title", "user__email")

