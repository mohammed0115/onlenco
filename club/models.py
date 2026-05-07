from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import CEFR_CHOICES


class ClubEvent(models.Model):
    title = models.CharField(max_length=200)
    topic = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    host_name = models.CharField(max_length=120, blank=True)
    level_min = models.CharField(max_length=2, choices=CEFR_CHOICES, default="A2")
    level_max = models.CharField(max_length=2, choices=CEFR_CHOICES, default="C1")
    starts_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    meet_url = models.URLField(blank=True)
    capacity = models.PositiveSmallIntegerField(default=20)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]

    @property
    def is_past(self):
        return self.starts_at < timezone.now()

    @property
    def ends_at(self):
        return self.starts_at + timedelta(minutes=self.duration_minutes)

    @property
    def is_full(self):
        return self.rsvps.filter(status="going").count() >= self.capacity

    def __str__(self):
        return f"{self.title} ({self.starts_at:%Y-%m-%d})"


class ClubRSVP(models.Model):
    STATUS_CHOICES = [("going", "Going"), ("maybe", "Maybe"), ("cancelled", "Cancelled")]

    event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="rsvps")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="club_rsvps",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="going")
    attended = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("event", "user")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.event} ({self.status})"

