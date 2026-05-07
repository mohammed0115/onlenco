from rest_framework import serializers

from ..models import NotificationPreference


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "learning_updates",
            "payment_updates",
            "weekly_summary",
            "admin_alerts",
            "marketing_emails",
            "language",
            "updated_at",
        ]
        read_only_fields = ["updated_at"]
