from django.conf import settings
from django.db import models


AI_FEATURE_CHOICES = [
    ("tutor", "Tutor"),
    ("placement", "Placement"),
    ("dictionary", "Dictionary"),
    ("error_analysis", "Error Analysis"),
    ("exercise_generation", "Exercise Generation"),
    ("other", "Other"),
]


class AIUsageLog(models.Model):
    """One row per outbound AI call (success or failure).

    Used for both cost-tracking and per-user daily limits. Keep this lean —
    no large prompt/response payloads, just the counts and metadata.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ai_usage_logs",
    )
    feature = models.CharField(max_length=30, choices=AI_FEATURE_CHOICES)
    model = models.CharField(max_length=80, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    success = models.BooleanField(default=True)
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "feature", "-created_at"]),
            models.Index(fields=["feature"]),
        ]

    def __str__(self):
        return f"AIUsage<{self.user_id}> {self.feature} ok={self.success}"
