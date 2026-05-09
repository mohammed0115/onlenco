from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


CEFR_CHOICES = [
    ("A0", "A0"), ("A1", "A1"), ("A2", "A2"),
    ("B1", "B1"), ("B2", "B2"), ("C1", "C1"), ("C2", "C2"),
    ("C3", _("C3 (Advanced communication)")),
]

SUBSCRIPTION_CHOICES = [
    ("inactive", _("Inactive")),
    ("pending",  _("Pending verification")),
    ("active",   _("Active")),
    ("expired",  _("Expired")),
]

ROLE_CHOICES = [
    ("student", _("Student")),
    ("admin",   _("Admin")),
]

ONBOARDING_PATH_CHOICES = [
    ("placement_test",  _("Placement test")),
    ("beginner_start",  _("Started from beginner")),
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
        verbose_name=_("User"),
    )
    full_name = models.CharField(
        max_length=120, blank=True, verbose_name=_("Full name"),
    )
    preferred_language = models.CharField(
        max_length=2,
        choices=[("en", _("English")), ("ar", _("Arabic"))],
        default="ar",
        verbose_name=_("Preferred language"),
    )
    role = models.CharField(
        max_length=10, choices=ROLE_CHOICES, default="student",
        verbose_name=_("Role"),
    )
    cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True, null=True,
        verbose_name=_("CEFR level"),
    )
    placement_completed = models.BooleanField(
        default=False, verbose_name=_("Placement completed"),
    )

    # --- Onboarding ----------------------------------------------------
    # `onboarding_completed` is the single gate for the post-signup
    # redirect rule — True when the student took the placement test
    # OR when they explicitly chose to start from beginner.
    onboarding_completed = models.BooleanField(
        default=False, verbose_name=_("Onboarding completed"),
    )
    onboarding_path = models.CharField(
        max_length=20, blank=True, choices=ONBOARDING_PATH_CHOICES,
        help_text=_("Which onboarding path the student picked."),
        verbose_name=_("Onboarding path"),
    )
    initial_cefr_level = models.CharField(
        max_length=2, choices=CEFR_CHOICES, blank=True, null=True,
        help_text=_("Level at onboarding. `cefr_level` is the live current level."),
        verbose_name=_("Initial CEFR level"),
    )
    onboarding_completed_at = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Onboarding completed at"),
    )

    email_verified = models.BooleanField(
        default=False, verbose_name=_("Email verified"),
    )
    subscription_status = models.CharField(
        max_length=10, choices=SUBSCRIPTION_CHOICES, default="inactive",
        verbose_name=_("Subscription status"),
    )
    subscription_expires_at = models.DateTimeField(
        blank=True, null=True, verbose_name=_("Subscription expires"),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Created at"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Updated at"))

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Profile")
        verbose_name_plural = _("Profiles")

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
