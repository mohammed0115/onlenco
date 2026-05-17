from django.contrib import admin

from .models import PlatformAuditLog, PlatformStudentFlag, PlatformStudentNote


@admin.register(PlatformAuditLog)
class PlatformAuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action_type", "object_type", "object_id", "target_user")
    list_filter = ("action_type", "object_type", "created_at")
    search_fields = ("description", "actor__email", "actor__username", "target_user__email", "target_user__username")
    raw_id_fields = ("actor", "target_user")
    readonly_fields = (
        "actor", "target_user", "action_type", "object_type", "object_id",
        "description", "metadata", "ip_address", "user_agent", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PlatformStudentFlag)
class PlatformStudentFlagAdmin(admin.ModelAdmin):
    list_display = ("user", "risk_status", "support_status", "is_deactivated_by_admin", "updated_at")
    list_filter = ("risk_status", "is_deactivated_by_admin")
    search_fields = ("user__email", "user__username", "support_status")
    raw_id_fields = ("user",)


@admin.register(PlatformStudentNote)
class PlatformStudentNoteAdmin(admin.ModelAdmin):
    list_display = ("student", "author", "is_private", "created_at")
    list_filter = ("is_private", "created_at")
    search_fields = ("student__email", "student__username", "author__email", "note")
    raw_id_fields = ("student", "author")
