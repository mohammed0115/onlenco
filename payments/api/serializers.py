from rest_framework import serializers

from payments.models import (
    PLAN_DETAILS,
    PaymentMethodAccount,
    PaymentSubmission,
)


class PlanSerializer(serializers.Serializer):
    code = serializers.CharField()
    price_sdg = serializers.IntegerField()
    duration_days = serializers.IntegerField()


class PaymentMethodAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethodAccount
        fields = [
            "method", "label", "account_number", "account_holder",
            "instructions", "is_active", "sort_order",
        ]


class PaymentSubmissionSerializer(serializers.ModelSerializer):
    screenshot = serializers.ImageField(required=True)

    class Meta:
        model = PaymentSubmission
        fields = [
            "id", "plan", "method", "transaction_reference",
            "amount_sdg", "screenshot", "status",
            "admin_note", "submitted_at", "reviewed_at",
        ]
        read_only_fields = [
            "id", "amount_sdg", "status", "admin_note",
            "submitted_at", "reviewed_at",
        ]

    def validate_plan(self, value):
        if value not in PLAN_DETAILS:
            raise serializers.ValidationError("Unknown plan")
        return value

    def validate_method(self, value):
        if not PaymentMethodAccount.objects.filter(method=value, is_active=True).exists():
            raise serializers.ValidationError("This payment method is not currently available.")
        return value

    def validate_screenshot(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image must be 5 MB or smaller.")

        allowed = {"image/png", "image/jpeg", "image/webp", "image/gif"}
        content_type = getattr(value, "content_type", "") or ""
        if content_type and content_type not in allowed:
            raise serializers.ValidationError(
                "Only PNG, JPEG, WEBP, or GIF images are accepted."
            )
        return value
