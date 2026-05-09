from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
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
    pronunciation_score = models.PositiveSmallIntegerField(null=True, blank=True)
    fluency_score = models.PositiveSmallIntegerField(null=True, blank=True)
    level = models.CharField(max_length=2, choices=CEFR_CHOICES)
    feedback = models.TextField(blank=True)
    transcript = models.JSONField(default=dict)
    audio = models.FileField(upload_to="placement/audio/%Y/%m/", blank=True, null=True)
    audio_transcript = models.TextField(blank=True)
    audio_duration_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Placement result")
        verbose_name_plural = _("Placement results")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} → {self.level} ({self.created_at:%Y-%m-%d})"
