"""Persistent record of a single voice turn from a student.

One row per uploaded audio blob. Carries the canonical transcript +
duration + confidence so the rest of the platform can audit speaking
performance without holding the audio open.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


SOURCE_CHOICES = [
    ("tutor",     _("AI Tutor")),
    ("placement", _("Placement")),
    ("lesson",    _("Lesson")),
    ("exam",      _("Exam")),
]


class SpeakingAttempt(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="speaking_attempts", verbose_name=_("User"),
    )
    audio_file = models.FileField(
        upload_to="speech/%Y/%m/", blank=True, null=True,
        verbose_name=_("Audio file"),
    )
    transcript = models.TextField(blank=True, verbose_name=_("Transcript"))
    duration_seconds = models.PositiveIntegerField(
        default=0, verbose_name=_("Duration (seconds)"),
    )
    confidence = models.FloatField(default=0.0, verbose_name=_("Confidence"))
    source = models.CharField(
        max_length=15, choices=SOURCE_CHOICES, default="tutor",
        verbose_name=_("Source"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["source", "-created_at"]),
        ]
        verbose_name = _("Speaking attempt")
        verbose_name_plural = _("Speaking attempts")

    def __str__(self):
        return f"SpeakAtt<{self.user_id}> {self.source} {self.duration_seconds}s"
