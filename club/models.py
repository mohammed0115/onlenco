from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
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
        verbose_name = _("Club event")
        verbose_name_plural = _("Club events")
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
    attendance_marked_at = models.DateTimeField(null=True, blank=True)
    attendance_marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="club_attendance_marks",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Club rsvp")
        verbose_name_plural = _("Club rsvps")
        unique_together = [("event", "user")]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user} — {self.event} ({self.status})"


class ClubFeedback(models.Model):
    """Teacher's note about a specific student after a club session.

    Distinct from ``ClubRSVP.attended`` — that's a boolean, this is the
    qualitative feedback (pronunciation, confidence, follow-ups).
    """

    event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="feedback_entries")
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="club_feedback_received",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="club_feedback_written",
    )
    rating = models.PositiveSmallIntegerField(
        default=3,
        help_text=_("1-5 quick rating of student's participation."),
    )
    feedback_en = models.TextField(blank=True)
    feedback_ar = models.TextField(blank=True)
    xp_awarded = models.PositiveIntegerField(default=0)
    is_visible_to_student = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Club feedback")
        verbose_name_plural = _("Club feedback entries")
        unique_together = [("event", "student")]
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "-created_at"]),
        ]

    def __str__(self):
        return f"feedback<{self.event_id}/{self.student_id}> r={self.rating}"

