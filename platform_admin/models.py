from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


RISK_STATUS_CHOICES = [
    ("normal", _("Normal")),
    ("watch", _("Watch")),
    ("at_risk", _("At risk")),
    ("critical", _("Critical")),
]


class PlatformAuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_audit_logs",
        verbose_name=_("Actor"),
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_audit_logs_targeting",
        verbose_name=_("Target user"),
    )
    action_type = models.CharField(max_length=80, db_index=True, verbose_name=_("Action type"))
    object_type = models.CharField(max_length=80, blank=True, db_index=True, verbose_name=_("Object type"))
    object_id = models.CharField(max_length=80, blank=True, db_index=True, verbose_name=_("Object ID"))
    description = models.TextField(blank=True, verbose_name=_("Description"))
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name=_("IP address"))
    user_agent = models.TextField(blank=True, verbose_name=_("User agent"))
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name=_("Created at"))

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["target_user", "-created_at"]),
            models.Index(fields=["action_type", "-created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]
        verbose_name = _("Platform audit log")
        verbose_name_plural = _("Platform audit logs")

    def __str__(self):
        return f"{self.action_type} @ {self.created_at:%Y-%m-%d %H:%M}"


class PlatformStudentFlag(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="platform_flag",
        verbose_name=_("Student"),
    )
    risk_status = models.CharField(
        max_length=12,
        choices=RISK_STATUS_CHOICES,
        default="normal",
        db_index=True,
        verbose_name=_("Risk status"),
    )
    support_status = models.CharField(max_length=40, blank=True, verbose_name=_("Support status"))
    is_deactivated_by_admin = models.BooleanField(default=False, verbose_name=_("Deactivated by admin"))
    metadata = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]
        verbose_name = _("Platform student flag")
        verbose_name_plural = _("Platform student flags")

    def __str__(self):
        return f"StudentFlag<{self.user_id}> {self.risk_status}"


class PlatformStudentNote(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="platform_notes",
        verbose_name=_("Student"),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_notes_authored",
        verbose_name=_("Author"),
    )
    note = models.TextField(verbose_name=_("Note"))
    is_private = models.BooleanField(default=False, verbose_name=_("Private"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "-created_at"]),
        ]
        verbose_name = _("Platform student note")
        verbose_name_plural = _("Platform student notes")

    def __str__(self):
        return f"Note<{self.student_id}> {self.created_at:%Y-%m-%d}"

