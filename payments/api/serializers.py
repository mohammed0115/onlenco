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
        read_only_fields = ["id", "status", "admin_note", "reviewed_at"]

    def validate_plan(self, value):
        if value not in PLAN_DETAILS:
            raise serializers.ValidationError("Unknown plan")
        return value

    def validate(self, attrs):
        plan = attrs.get("plan")
        if plan and "amount_sdg" in attrs:
            expected = PLAN_DETAILS[plan]["price_sdg"]
            if attrs["amount_sdg"] != expected:
                raise serializers.ValidationError(
                    {"amount_sdg": f"Expected {expected} SDG for plan '{plan}'."}
                )
        return attrs
