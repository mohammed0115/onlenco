from django.conf import settings
from django.db import models

from accounts.models import CEFR_CHOICES


class PlacementResult(models.Model):
    """Stored result of one AI placement assessment."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="placement_results",
    )
    written_score = models.PositiveSmallIntegerField(null=True, blank=True)
    speaking_score = models.PositiveSmallIntegerField(null=True, blank=True)
    level = models.CharField(max_length=2, choices=CEFR_CHOICES)
    feedback = models.TextField(blank=True)
    transcript = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.level} ({self.created_at:%Y-%m-%d})"
