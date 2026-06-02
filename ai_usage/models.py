"""Data layer for AI usage accounting & cost control (Prompt 12A).

Four models:

* ``AIModelPricing``      — admin-editable price book (per provider+model+date).
* ``AIUsageLog``          — one row per AI request (success / failed / cancelled).
* ``AIDailyUsageSummary`` — nightly rollup of the logs (per user/org/role/day).
* ``StudentDailyAILimit`` — denormalised per-student daily minute projection,
                            sourced from the ``subscriptions`` app.

Design rules:
* Money is ``Decimal`` everywhere — never float.
* No raw prompts/responses are stored (privacy). ``metadata`` is minimal.
* ``organization`` is a plain slug string (the project has no tenancy model
  yet); it is kept on every model for forward-compatibility.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from . import constants as C

# Money: 18 digits, 6 decimal places (sub-cent precision for per-token math).
_MONEY = dict(max_digits=18, decimal_places=6)
# Minutes: keep one decimal place of seconds-derived precision.
_MINUTES = dict(max_digits=10, decimal_places=2)


class AIModelPricing(models.Model):
    """Admin-editable price book. Active row chosen by provider+model+date.

    Never hardcode prices in services — read them from here.
    """

    provider = models.CharField(
        max_length=16, choices=C.PROVIDER_CHOICES, default=C.PROVIDER_OPENAI,
        db_index=True,
    )
    model_name = models.CharField(max_length=128, db_index=True)

    input_price_per_1m_tokens = models.DecimalField(
        default=Decimal("0"), help_text=_("USD per 1,000,000 input/prompt tokens."),
        **_MONEY,
    )
    output_price_per_1m_tokens = models.DecimalField(
        default=Decimal("0"), help_text=_("USD per 1,000,000 output/completion tokens."),
        **_MONEY,
    )
    audio_input_price_per_minute = models.DecimalField(
        null=True, blank=True, help_text=_("USD per minute of input audio (STT / realtime in)."),
        **_MONEY,
    )
    audio_output_price_per_minute = models.DecimalField(
        null=True, blank=True, help_text=_("USD per minute of output audio (TTS / realtime out)."),
        **_MONEY,
    )
    # Image generation pricing (Prompt 16.5). Per-image or per-1k-images.
    image_price_per_generation = models.DecimalField(
        null=True, blank=True, help_text=_("USD per generated image."), **_MONEY,
    )
    image_price_per_1k_images = models.DecimalField(
        null=True, blank=True, help_text=_("USD per 1,000 generated images (alt unit)."), **_MONEY,
    )
    image_pricing_unit = models.CharField(
        max_length=16, default="per_image",
        choices=[("per_image", _("Per image")), ("per_1k_images", _("Per 1k images"))],
        help_text=_("Which image price field to use."),
    )

    currency = models.CharField(max_length=8, default="USD")
    is_active = models.BooleanField(default=True, db_index=True)
    effective_from = models.DateTimeField(default=timezone.now, db_index=True)
    effective_to = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("AI model pricing")
        verbose_name_plural = _("AI model pricing")
        ordering = ["provider", "model_name", "-effective_from"]
        indexes = [
            models.Index(fields=["provider", "model_name", "is_active"]),
            models.Index(fields=["provider", "model_name", "effective_from"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.model_name} (from {self.effective_from:%Y-%m-%d})"

    @classmethod
    def get_active(cls, provider: str, model_name: str, at_datetime=None):
        """Return the pricing row in effect for (provider, model) at a time.

        Picks the active row whose effective window contains ``at_datetime``,
        most-recent ``effective_from`` first. Returns ``None`` when no row
        matches — callers MUST treat that as "cost unknown → 0 + warning",
        never as an error.
        """
        when = at_datetime or timezone.now()
        qs = cls.objects.filter(
            provider=provider, model_name=model_name, is_active=True,
            effective_from__lte=when,
        ).filter(
            models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=when)
        ).order_by("-effective_from")
        return qs.first()


class AIUsageLog(models.Model):
    """One row per AI request. Written for success, failure, and cancellation.

    NOTE: distinct from the legacy ``core.models.AIUsageLog`` (a lighter table
    kept for backward compatibility during migration). This is the richer,
    cost-aware log that the centralised wrapper writes.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="ai_usage_entries",
    )
    organization = models.CharField(max_length=64, blank=True, default="", db_index=True)
    role = models.CharField(max_length=16, choices=C.ROLE_CHOICES, default=C.ROLE_STUDENT)
    feature = models.CharField(max_length=32, choices=C.FEATURE_CHOICES, default=C.FEATURE_OTHER)

    provider = models.CharField(max_length=16, choices=C.PROVIDER_CHOICES, default=C.PROVIDER_OPENAI)
    model_name = models.CharField(max_length=128, blank=True, default="")

    request_id = models.CharField(max_length=128, null=True, blank=True, unique=True)
    session_id = models.CharField(max_length=128, blank=True, default="")
    lesson_id = models.PositiveIntegerField(null=True, blank=True)
    unit_id = models.PositiveIntegerField(null=True, blank=True)
    course_id = models.PositiveIntegerField(null=True, blank=True)

    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    total_tokens = models.PositiveIntegerField(default=0)
    audio_input_seconds = models.PositiveIntegerField(default=0)
    audio_output_seconds = models.PositiveIntegerField(default=0)

    ai_minutes_used = models.DecimalField(default=Decimal("0"), **_MINUTES)
    estimated_cost_usd = models.DecimalField(default=Decimal("0"), **_MONEY)

    status = models.CharField(max_length=12, choices=C.STATUS_CHOICES, default=C.STATUS_SUCCESS)
    error_message = models.CharField(max_length=500, blank=True, default="")
    latency_ms = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    usage_date = models.DateField(db_index=True, default=timezone.localdate)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("AI usage log")
        verbose_name_plural = _("AI usage logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["usage_date"]),
            models.Index(fields=["user", "usage_date"]),
            models.Index(fields=["feature", "usage_date"]),
            models.Index(fields=["model_name", "usage_date"]),
            models.Index(fields=["organization", "usage_date"]),
            models.Index(fields=["status", "usage_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.feature}/{self.model_name} {self.status} ${self.estimated_cost_usd}"

    def save(self, *args, **kwargs):
        # Keep total_tokens & usage_date self-consistent without forcing callers.
        if not self.total_tokens:
            self.total_tokens = (self.input_tokens or 0) + (self.output_tokens or 0)
        if self.usage_date is None:
            self.usage_date = (self.created_at or timezone.now()).date()
        super().save(*args, **kwargs)


class AIDailyUsageSummary(models.Model):
    """Nightly rollup of ``AIUsageLog`` per (date, user, organization, role)."""

    date = models.DateField(db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="ai_daily_summaries",
    )
    organization = models.CharField(max_length=64, blank=True, default="", db_index=True)
    role = models.CharField(max_length=16, choices=C.ROLE_CHOICES, default=C.ROLE_STUDENT)

    total_requests = models.PositiveIntegerField(default=0)
    successful_requests = models.PositiveIntegerField(default=0)
    failed_requests = models.PositiveIntegerField(default=0)

    input_tokens = models.PositiveBigIntegerField(default=0)
    output_tokens = models.PositiveBigIntegerField(default=0)
    total_tokens = models.PositiveBigIntegerField(default=0)

    ai_minutes_used = models.DecimalField(default=Decimal("0"), **_MINUTES)
    estimated_cost_usd = models.DecimalField(default=Decimal("0"), **_MONEY)

    ai_tutor_minutes_used = models.DecimalField(default=Decimal("0"), **_MINUTES)
    placement_minutes_used = models.DecimalField(default=Decimal("0"), **_MINUTES)
    content_generation_cost = models.DecimalField(default=Decimal("0"), **_MONEY)

    top_feature = models.JSONField(default=dict, blank=True)
    top_model = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("AI daily usage summary")
        verbose_name_plural = _("AI daily usage summaries")
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["date", "user", "organization", "role"],
                name="unique_ai_daily_summary",
            ),
        ]
        indexes = [
            models.Index(fields=["date", "role"]),
            models.Index(fields=["organization", "date"]),
        ]

    def __str__(self) -> str:
        who = self.user_id or "all"
        return f"{self.date} {self.role} user={who} ${self.estimated_cost_usd}"


class StudentDailyAILimit(models.Model):
    """Per-student per-day AI-Tutor minute projection.

    This is a *denormalised cache* over the authoritative
    ``subscriptions`` quota system (plan minutes + one-shot free trial +
    ``UserDailyQuota``). It is refreshed by ``limit_service`` on read and
    by the nightly ``update_student_daily_limits`` command. It never
    stores money and is safe to expose (remaining minutes) to students.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="ai_daily_limits",
    )
    date = models.DateField(db_index=True, default=timezone.localdate)
    plan_name = models.CharField(max_length=128, blank=True, default="")

    allowed_minutes = models.DecimalField(default=Decimal("0"), **_MINUTES)
    used_minutes = models.DecimalField(default=Decimal("0"), **_MINUTES)
    remaining_minutes = models.DecimalField(default=Decimal("0"), **_MINUTES)

    is_free_first_day = models.BooleanField(default=False)
    is_exceeded = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Student daily AI limit")
        verbose_name_plural = _("Student daily AI limits")
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["student", "date"], name="unique_student_daily_ai_limit",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.student_id} @ {self.date}: {self.remaining_minutes}/{self.allowed_minutes}m left"
