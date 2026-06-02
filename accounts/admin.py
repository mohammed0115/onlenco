from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import Profile, StudentApprovalEvent


@admin.register(StudentApprovalEvent)
class StudentApprovalEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "action", "old_status", "new_status",
                    "actor", "ip_address")
    list_filter = ("action", "new_status")
    search_fields = ("user__username", "user__email", "note")
    readonly_fields = [f.name for f in StudentApprovalEvent._meta.fields]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "full_name",
        "role",
        "approval_status",
        "cefr_level",
        "initial_cefr_level",
        "onboarding_path",
        "onboarding_completed",
        "subscription_state",
        "expires_in_days",
        "placement_completed",
        "created_at",
    )
    list_filter = (
        "role", "subscription_status", "cefr_level",
        "placement_completed", "onboarding_completed", "onboarding_path",
    )
    search_fields = ("full_name", "user__email", "user__username")
    readonly_fields = ("created_at", "updated_at", "onboarding_completed_at")
    actions = ["reset_onboarding"]

    @admin.action(description="Reset onboarding (let student choose again)")
    def reset_onboarding(self, request, queryset):
        n = queryset.update(
            onboarding_completed=False,
            onboarding_path="",
            onboarding_completed_at=None,
        )
        self.message_user(request, f"Reset onboarding for {n} student(s).")

    @admin.display(description="Subscription")
    def subscription_state(self, obj):
        now = timezone.now()
        if obj.subscription_status == "active":
            if obj.subscription_expires_at and obj.subscription_expires_at <= now:
                return "✗ Expired"
            if obj.subscription_expires_at and obj.subscription_expires_at <= now + timedelta(days=7):
                return "⚠ Expiring soon"
            return "✓ Active"
        if obj.subscription_status == "expired":
            return "✗ Expired"
        if obj.subscription_status == "pending":
            return "Pending"
        return "Inactive"

    @admin.display(description="Expires")
    def expires_in_days(self, obj):
        if obj.subscription_expires_at is None:
            return "—"
        delta = obj.subscription_expires_at - timezone.now()
        days = int(delta.total_seconds() // 86400)
        if days < 0:
            return f"Expired {abs(days)} days ago"
        return f"Expires in {days} days"
