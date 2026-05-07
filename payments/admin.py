from django import forms
from django.contrib import admin, messages

from .models import PaymentMethodAccount, PaymentSubmission


class PaymentSubmissionAdminForm(forms.ModelForm):
    class Meta:
        model = PaymentSubmission
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        note = (cleaned.get("admin_note") or "").strip()

        if status == "rejected" and not note:
            self.add_error("admin_note", "Admin note is required when rejecting a payment.")

        return cleaned


@admin.register(PaymentSubmission)
class PaymentSubmissionAdmin(admin.ModelAdmin):
    form = PaymentSubmissionAdminForm
    list_display = ("user", "plan", "method", "amount_sdg",
                    "status", "created_at", "reviewed_at")
    list_filter = ("status", "method", "plan")
    search_fields = ("user__email", "user__username", "transaction_reference")
    readonly_fields = ("user", "plan", "method", "amount_sdg",
                       "transaction_reference", "screenshot",
                       "created_at", "reviewed_at", "reviewed_by")
    fieldsets = (
        (None, {
            "fields": ("user", "plan", "method", "amount_sdg",
                       "transaction_reference", "screenshot",
                       "status", "admin_note"),
        }),
        ("Review metadata", {
            "fields": ("created_at", "reviewed_at", "reviewed_by"),
        }),
    )
    actions = ("approve_payments", "reject_payments")

    def save_model(self, request, obj, form, change):
        if not change:
            return super().save_model(request, obj, form, change)

        if "status" not in form.changed_data:
            return super().save_model(request, obj, form, change)

        original_status = PaymentSubmission.objects.only("status").get(pk=obj.pk).status
        new_status = obj.status

        if original_status == "pending" and new_status == "approved":
            PaymentSubmission.objects.get(pk=obj.pk).approve(reviewer=request.user)
            return

        if original_status == "pending" and new_status == "rejected":
            note = (form.cleaned_data.get("admin_note") or "").strip()
            PaymentSubmission.objects.get(pk=obj.pk).reject(reviewer=request.user, note=note)
            return

        return super().save_model(request, obj, form, change)

    @admin.action(description="✓ Approve selected payments (activates subscription)")
    def approve_payments(self, request, queryset):
        count = 0
        for payment in queryset.filter(status="pending"):
            payment.approve(reviewer=request.user)
            count += 1
        self.message_user(
            request,
            f"Approved {count} payment(s) and activated subscriptions.",
            level=messages.SUCCESS,
        )

    @admin.action(description="✗ Reject selected payments")
    def reject_payments(self, request, queryset):
        count = 0
        for payment in queryset.filter(status="pending"):
            payment.reject(reviewer=request.user, note="Rejected by admin.")
            count += 1
        self.message_user(
            request,
            f"Rejected {count} payment(s).",
            level=messages.WARNING,
        )


@admin.register(PaymentMethodAccount)
class PaymentMethodAccountAdmin(admin.ModelAdmin):
    list_display = (
        "method",
        "label",
        "account_number",
        "account_holder",
        "is_active",
        "sort_order",
    )
    list_filter = ("is_active",)
    list_editable = ("is_active", "sort_order")
    search_fields = ("label", "account_number", "account_holder")
    ordering = ("sort_order", "method")

