from django.contrib import admin, messages

from .models import (
    EmailNotification,
    EmailVerificationToken,
    NotificationEvent,
    NotificationPreference,
    NotificationTemplate,
)


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "expires_at", "used_at", "created_at")
    search_fields = ("user__email", "user__username", "token")
    readonly_fields = ("user", "token", "expires_at", "used_at", "created_at")


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "user", "status", "priority", "created_at", "processed_at")
    list_filter = ("event_type", "status", "priority")
    search_fields = ("event_type", "user__email", "user__username", "error_message")
    readonly_fields = ("created_at", "processed_at", "error_message")
    date_hierarchy = "created_at"


@admin.register(EmailNotification)
class EmailNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "recipient_email",
        "subject",
        "language",
        "status",
        "attempts_count",
        "sent_at",
        "created_at",
    )
    list_filter = ("status", "language", "template_name")
    search_fields = ("recipient_email", "subject", "error_message", "user__email")
    readonly_fields = (
        "event",
        "user",
        "recipient_email",
        "recipient_name",
        "subject",
        "template_name",
        "language",
        "metadata",
        "created_at",
        "sent_at",
        "last_attempt_at",
        "attempts_count",
        "error_message",
    )
    date_hierarchy = "created_at"
    actions = ["retry_failed_emails"]

    @admin.action(description="Retry sending selected failed emails")
    def retry_failed_emails(self, request, queryset):
        from .services.notification_service import NotificationService

        retried = 0
        skipped = 0
        for email in queryset:
            if email.status != "failed":
                skipped += 1
                continue
            NotificationService().retry_failed_email(email)
            retried += 1
        self.message_user(
            request,
            f"Retried {retried} email(s); skipped {skipped} (not in failed status).",
            level=messages.INFO,
        )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "language",
        "learning_updates",
        "payment_updates",
        "weekly_summary",
        "admin_alerts",
        "marketing_emails",
        "updated_at",
    )
    list_filter = ("language", "learning_updates", "payment_updates", "weekly_summary")
    search_fields = ("user__email", "user__username")


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("event_type", "language", "subject", "template_name", "is_active", "updated_at")
    list_filter = ("language", "is_active", "event_type")
    search_fields = ("event_type", "subject", "template_name")
