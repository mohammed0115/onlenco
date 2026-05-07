from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


CEFR_CHOICES = [
    ("A0", "A0"), ("A1", "A1"), ("A2", "A2"),
    ("B1", "B1"), ("B2", "B2"), ("C1", "C1"), ("C2", "C2"),
    ("C3", "C3 (Advanced communication)"),
]

SUBSCRIPTION_CHOICES = [
    ("inactive", "Inactive"),
    ("pending", "Pending verification"),
    ("active", "Active"),
    ("expired", "Expired"),
]

ROLE_CHOICES = [
    ("student", "Student"),
    ("admin", "Admin"),
]


class Profile(models.Model):
    """One-to-one profile extension for the built-in User model.

    Django's built-in User handles email/password/sessions. This model
    holds everything specific to Onlenco: CEFR level, subscription
    status, language preference, and the student/admin role flag.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    full_name = models.CharField(max_length=120, blank=True)
    preferred_language = models.CharField(
        max_length=2,
        choices=[("en", "English"), ("ar", "Arabic")],
        default="en",
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="student")
    cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True, null=True
    )
    placement_completed = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    subscription_status = models.CharField(
        max_length=10, choices=SUBSCRIPTION_CHOICES, default="inactive"
    )
    subscription_expires_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name or self.user.email or self.user.username}"

    @property
    def is_admin(self):
        return self.role == "admin" or self.user.is_staff

    @property
    def is_subscribed(self):
        """True if the subscription is currently active and not expired."""
        if self.subscription_status != "active":
            return False
        if self.subscription_expires_at is None:
            return True
        from django.utils import timezone
        return self.subscription_expires_at > timezone.now()


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile(sender, instance, created, **kwargs):
    """Auto-create a Profile when a new User is created."""
    if created:
        Profile.objects.get_or_create(user=instance)
