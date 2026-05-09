"""Auditable log of every router call.

One row per `route_task()` invocation — captures:
- which provider eventually served the request
- whether earlier providers were skipped
- end-to-end latency
- the user (when known)
- error_message + success flag for failed runs

Used for cost-tracking dashboards (how often does OpenAI win?), latency
SLOs, and post-hoc debugging when a model output looks wrong.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models

from django.utils.translation import gettext_lazy as _
from . import constants as C


class ProviderKillSwitch(models.Model):
    """Operator-controlled kill switch for the model router.

    Each row disables one `(task_type, provider)` pair. The router
    checks this table at call time, so flipping `disabled=True` takes
    effect on the very next request — no deploy, no settings reload.

    A wildcard row with `task_type="*"` disables the provider across
    all tasks. Useful as an emergency "stop calling OpenAI right now"
    button when usage spikes or the upstream API is acting up.
    """

    task_type = models.CharField(
        max_length=24,
        help_text="One of the registered task types, or '*' for all.",
    )
    provider = models.CharField(max_length=20, choices=C.PROVIDER_CHOICES)
    disabled = models.BooleanField(
        default=True,
        help_text="True = provider is skipped by the router for this task.",
    )
    reason = models.CharField(max_length=200, blank=True)
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Auto-clear time. Null = stays disabled until manually re-enabled.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Provider kill switch")
        verbose_name_plural = _("Provider kill switches")
        ordering = ["task_type", "provider"]
        constraints = [
            models.UniqueConstraint(
                fields=["task_type", "provider"],
                name="ai_engine_kill_switch_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["task_type", "provider"]),
            models.Index(fields=["disabled"]),
        ]

    def __str__(self):
        state = "DISABLED" if self.disabled else "enabled"
        return f"Switch<{self.task_type}/{self.provider}: {state}>"


class ModelPredictionLog(models.Model):
    task_type = models.CharField(max_length=24, choices=C.TASK_TYPE_CHOICES)
    provider = models.CharField(max_length=20, choices=C.PROVIDER_CHOICES,
                                default=C.P_NONE)
    confidence = models.FloatField(default=0.0)
    fallback_used = models.BooleanField(default=False)
    latency_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="model_predictions",
    )
    error_message = models.TextField(blank=True)
    model_version = models.CharField(max_length=80, blank=True)
    reason = models.CharField(max_length=120, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Model prediction log")
        verbose_name_plural = _("Model prediction logs")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task_type", "-created_at"]),
            models.Index(fields=["provider", "-created_at"]),
            models.Index(fields=["success"]),
            models.Index(fields=["fallback_used"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return (f"PredLog<{self.id}> {self.task_type}/{self.provider} "
                f"conf={self.confidence:.2f} success={self.success}")
