from django.conf import settings
from django.db import models

from . import constants as C


LANGUAGE_CHOICES = [("en", "English"), ("ar", "Arabic")]


class NotificationEvent(models.Model):
    """A logical event that may produce zero or more outbound emails.

    Created by `NotificationService.trigger`. Stays around as the audit
    record even if no email is sent (skipped due to preferences, missing
    email, or duplicate suppression).
    """

    event_type = models.CharField(max_length=64, choices=C.EVENT_TYPE_CHOICES)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_events",
        help_text="The student/admin the event is about. Null for system events.",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_events_actor",
        help_text="The user who caused the event (e.g. an admin approving a payment).",
    )
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=15, choices=C.EVENT_STATUS_CHOICES, default=C.STATUS_PENDING
    )
    priority = models.CharField(
        max_length=10, choices=C.PRIORITY_CHOICES, default=C.PRIORITY_NORMAL
    )
    error_message = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["user", "event_type"]),
        ]

    def __str__(self):
        return f"NotificationEvent<{self.id}> {self.event_type} {self.status}"


class EmailNotification(models.Model):
    """A single outbound email tied to a NotificationEvent.

    One event may produce many emails (e.g. notify_admins fans out).
    """

    event = models.ForeignKey(
        NotificationEvent,
        on_delete=models.CASCADE,
        related_name="emails",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_notifications",
    )
    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=120, blank=True)
    subject = models.CharField(max_length=255)
    template_name = models.CharField(max_length=120)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="en")
    status = models.CharField(
        max_length=10, choices=C.EMAIL_STATUS_CHOICES, default=C.STATUS_PENDING
    )
    attempts_count = models.PositiveSmallIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=500, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["recipient_email"]),
            models.Index(fields=["template_name"]),
        ]

    def __str__(self):
        return f"EmailNotification<{self.id}> → {self.recipient_email} {self.status}"


class NotificationPreference(models.Model):
    """Per-user preferences. Auto-created lazily by `PreferenceService`."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notification_preference",
    )
    learning_updates = models.BooleanField(default=True)
    payment_updates = models.BooleanField(default=True)
    weekly_summary = models.BooleanField(default=True)
    admin_alerts = models.BooleanField(
        default=True,
        help_text="Only honored for staff/admin recipients.",
    )
    marketing_emails = models.BooleanField(default=False)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="en")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"NotificationPreference<{self.user_id}>"


class EmailVerificationToken(models.Model):
    """Single-use token sent in the email_verification email."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_verification_tokens",
    )
    token = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "-created_at"])]

    def is_valid(self) -> bool:
        from django.utils import timezone
        return self.used_at is None and self.expires_at > timezone.now()

    def __str__(self):
        return f"VerifyToken<{self.user_id}> used={bool(self.used_at)}"


class NotificationTemplate(models.Model):
    """Optional override for default subjects/templates per (event, language).

    The renderer falls back to constants.DEFAULT_SUBJECTS / TEMPLATE_NAMES
    when no row exists. Useful for marketing teams to tweak copy without a
    deploy.
    """

    event_type = models.CharField(max_length=64, choices=C.EVENT_TYPE_CHOICES)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="en")
    subject = models.CharField(max_length=255)
    template_name = models.CharField(
        max_length=120,
        help_text="Path under templates/notifications/emails/ — e.g. welcome.html",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event_type", "language"],
                name="unique_template_per_event_language",
            )
        ]

    def __str__(self):
        return f"Template<{self.event_type}/{self.language}> {self.template_name}"
