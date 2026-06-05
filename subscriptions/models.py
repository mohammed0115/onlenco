"""Subscription plans, user subscriptions, and per-day usage quotas.

Sprint 1 foundation: defines the data layer for the AI-Tutor-minutes
business model. The actual deduction of seconds during a tutor session
is wired in Sprint 2; this app supplies the plan catalogue + the daily
counter that Sprint 2 will read/write.

Design notes:
  * Plans are admin-editable (no hard-coded prices or minute limits).
  * Quotas live in their own table keyed on (user, date) so each day is
    a clean row — easier to audit, easier to roll back accidental
    deductions, and avoids race conditions vs. cache-only counters.
  * UserSubscription is intentionally narrow: which plan is active for
    which window. Payment data stays in the ``payments`` app — they are
    linked but not fused, so plan changes don't require migrating
    historical payments.
"""
from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


SUBSCRIPTION_STATUS_CHOICES = [
    ("pending", _("Pending payment")),
    ("active", _("Active")),
    ("expired", _("Expired")),
    ("cancelled", _("Cancelled")),
]


class SubscriptionPlan(models.Model):
    """An admin-managed subscription tier.

    The 4 seed plans (5 / 10 / 15 / 30 daily AI-Tutor minutes) are loaded
    via data migration; admins can add / edit / disable plans without
    touching code.
    """

    code = models.SlugField(
        max_length=64, unique=True,
        help_text=_("Stable identifier used by code; never shown to users."),
    )
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    description_en = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)

    price_sdg = models.PositiveIntegerField(
        default=0,
        help_text=_("Monthly price in SDG. 0 means free."),
    )
    currency = models.CharField(max_length=8, default="SDG")
    billing_cycle = models.CharField(
        max_length=16,
        default="monthly",
        choices=[("monthly", _("Monthly")), ("quarterly", _("Quarterly"))],
    )

    ai_tutor_daily_minutes = models.PositiveIntegerField(
        default=0,
        help_text=_("Daily AI-Tutor minute allowance. 0 = AI Tutor blocked."),
    )
    library_audio_daily_minutes = models.PositiveIntegerField(
        default=0,
        help_text=_("Daily natural-reader audio allowance. 0 = blocked."),
    )

    is_active = models.BooleanField(default=True, db_index=True)
    is_free_trial = models.BooleanField(
        default=False,
        help_text=_("If true, this plan is awarded once per user and never renews."),
    )
    is_featured = models.BooleanField(
        default=False,
        help_text=_("Highlight this plan as 'most popular' on the public pricing page."),
    )
    sort_order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "ai_tutor_daily_minutes", "price_sdg"]
        verbose_name = _("Subscription plan")
        verbose_name_plural = _("Subscription plans")

    def __str__(self):
        return f"{self.name_en} ({self.ai_tutor_daily_minutes}m/day)"


class UserSubscription(models.Model):
    """Which plan is currently entitling which user.

    A user can have many rows historically (one per billing cycle), but
    only one *active* row at a time — enforced at the service layer via
    ``SubscriptionService.activate``.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=16,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=False)
    payment = models.ForeignKey(
        "payments.PaymentSubmission",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="subscriptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["end_date"]),
        ]
        verbose_name = _("User subscription")
        verbose_name_plural = _("User subscriptions")

    def __str__(self):
        return f"{self.user_id} → {self.plan.code} ({self.status})"

    @property
    def is_currently_active(self) -> bool:
        if self.status != "active":
            return False
        if self.end_date is not None and self.end_date <= timezone.now():
            return False
        return True


class FreeTrialUsage(models.Model):
    """One-shot AI-Tutor free trial — granted once per user, never resets.

    Independent of the daily-quota system: the subscription path uses
    UserDailyQuota (resets nightly), the trial path uses this row (a
    single bucket of seconds that empties forever once consumed).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="free_trial_usage",
    )
    free_seconds_granted = models.PositiveIntegerField(
        default=0,
        help_text=_("Total trial seconds awarded (typically 5 minutes = 300s)."),
    )
    free_seconds_used = models.PositiveIntegerField(default=0)
    is_consumed = models.BooleanField(
        default=False, db_index=True,
        help_text=_("True once the trial bucket is empty."),
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Free trial usage")
        verbose_name_plural = _("Free trial usages")

    def __str__(self):
        return f"{self.user_id}: {self.free_seconds_used}/{self.free_seconds_granted}s"

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.free_seconds_granted - self.free_seconds_used)


class AITutorSession(models.Model):
    """A single AI-Tutor session (voice or chat) — DB-backed lifecycle.

    Replaces the cache-only counter in tutor.services.realtime_session
    with a durable record. Each row covers exactly one session from
    start to end, and the partial unique constraint below prevents a
    user from running two concurrent in-progress sessions.
    """

    SOURCE_CHOICES = [
        ("voice_call", _("Voice call")),
        ("chat", _("Text chat")),
        # Placement speaking test — free of the AI-Tutor minute allowance.
        ("placement_voice", _("Placement speaking")),
    ]
    STATUS_CHOICES = [
        ("in_progress", _("In progress")),
        ("completed", _("Completed")),
        ("cancelled", _("Cancelled")),
        ("killed_quota_exceeded", _("Stopped — quota exceeded")),
    ]
    QUOTA_SOURCE_CHOICES = [
        ("subscription", _("Subscription daily quota")),
        ("free_trial", _("One-shot free trial")),
        ("none", _("No quota — refused")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_tutor_sessions",
    )
    source = models.CharField(max_length=16, choices=SOURCE_CHOICES, default="voice_call")
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES,
        default="in_progress", db_index=True,
    )
    quota_source = models.CharField(
        max_length=16, choices=QUOTA_SOURCE_CHOICES, default="none",
        help_text=_("Where the quota was deducted from at end-of-session."),
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    consumed_seconds = models.PositiveIntegerField(default=0)
    remaining_after_seconds = models.PositiveIntegerField(default=0)
    voice = models.CharField(max_length=32, blank=True)
    conversation_id = models.PositiveIntegerField(null=True, blank=True)
    voice_profile = models.ForeignKey(
        "subscriptions.VoiceProfile",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="tutor_sessions",
    )
    avatar_profile = models.ForeignKey(
        "subscriptions.AvatarProfile",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="tutor_sessions",
    )

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            # At most one in-progress session per user.
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(status="in_progress"),
                name="unique_in_progress_tutor_session_per_user",
            ),
        ]
        verbose_name = _("AI tutor session")
        verbose_name_plural = _("AI tutor sessions")

    def __str__(self):
        return f"session<{self.pk}> user={self.user_id} status={self.status}"


class VoiceProfile(models.Model):
    """Catalog of voices the AI Tutor can speak in.

    Each row maps a user-facing label (e.g. "Layla — Calm Teacher") to an
    upstream voice identifier the provider understands (currently OpenAI:
    alloy, echo, fable, onyx, nova, shimmer). Admins add/remove voices
    from the Control Center without code changes.
    """

    VOICE_TYPE_CHOICES = [
        ("male", _("Male")),
        ("female", _("Female")),
        ("neutral", _("Neutral")),
    ]
    STYLE_CHOICES = [
        ("calm_teacher", _("Calm Teacher")),
        ("friendly_tutor", _("Friendly Tutor")),
        ("energetic_coach", _("Energetic Coach")),
        ("professional", _("Professional Instructor")),
    ]
    ACCENT_CHOICES = [
        ("neutral", _("Neutral English")),
        ("british", _("British English")),
        ("american", _("American English")),
        ("african", _("African English Style")),
        ("asian", _("Asian English Style")),
        ("arabic_friendly", _("Arabic-friendly English Tutor")),
    ]
    TONE_CHOICES = [
        ("normal", _("Normal")),
        ("calm", _("Calm")),
        ("energetic", _("Energetic")),
        ("deep", _("Deep")),
        ("soft", _("Soft")),
    ]

    code = models.SlugField(max_length=64, unique=True)
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    description_en = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)
    provider_voice_id = models.CharField(
        max_length=64,
        help_text=_("Upstream voice ID (e.g. 'alloy', 'nova') passed to the model."),
    )
    voice_type = models.CharField(max_length=16, choices=VOICE_TYPE_CHOICES, default="neutral")
    style = models.CharField(max_length=24, choices=STYLE_CHOICES, default="friendly_tutor")
    accent = models.CharField(max_length=24, choices=ACCENT_CHOICES, default="neutral")
    tone = models.CharField(max_length=16, choices=TONE_CHOICES, default="normal")
    preview_audio_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name_en"]
        verbose_name = _("Voice profile")
        verbose_name_plural = _("Voice profiles")

    def __str__(self):
        return f"{self.name_en} ({self.provider_voice_id})"


class AvatarProfile(models.Model):
    """Catalog of on-screen avatars shown during the tutor session.

    Sprint 3 ships still images; Sprint 4 layers lip-sync video on top by
    adding ``video_url`` payloads that already match the avatar id here.
    """

    GENDER_CHOICES = [
        ("male", _("Male")),
        ("female", _("Female")),
        ("neutral", _("Neutral")),
    ]
    AVATAR_STYLE_CHOICES = [
        ("casual", _("Casual")),
        ("professional", _("Professional")),
        ("energetic", _("Energetic")),
    ]

    code = models.SlugField(max_length=64, unique=True)
    name_en = models.CharField(max_length=120)
    name_ar = models.CharField(max_length=120)
    description_en = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)
    gender = models.CharField(max_length=16, choices=GENDER_CHOICES, default="neutral")
    style = models.CharField(max_length=24, choices=AVATAR_STYLE_CHOICES, default="casual")
    image_url = models.URLField(blank=True)
    image_file = models.ImageField(
        upload_to="avatars/%Y/%m/",
        blank=True, null=True,
        help_text=_("Upload a square photo of the avatar's face — used by the voice-call screen."),
    )
    lipsync_video_url = models.URLField(
        blank=True,
        help_text=_("Optional looping idle/lipsync video. Sprint 4 wires this."),
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name_en"]
        verbose_name = _("Avatar profile")
        verbose_name_plural = _("Avatar profiles")

    def __str__(self):
        return self.name_en

    @property
    def effective_image_url(self) -> str:
        """Uploaded file wins over the URL field — admins typically upload
        a real photo from the Control Center."""
        if self.image_file:
            try:
                return self.image_file.url
            except Exception:
                pass
        return self.image_url or ""


class UserAIPreference(models.Model):
    """Per-user choice of voice + avatar + speed/pitch for the AI Tutor.

    One row per user. The fields are intentionally narrow — anything that
    is not specific to *this* user's pick (e.g. accent metadata) lives on
    VoiceProfile / AvatarProfile. ``sound_effects_enabled`` is wired in
    Sprint 5 (gamification audio cues).
    """

    SPEED_CHOICES = [
        ("slow", _("Slow")),
        ("normal", _("Normal")),
        ("fast", _("Fast")),
    ]
    PITCH_CHOICES = [
        ("low", _("Low")),
        ("normal", _("Normal")),
        ("high", _("High")),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_preference",
    )
    voice_profile = models.ForeignKey(
        VoiceProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="user_preferences",
    )
    avatar_profile = models.ForeignKey(
        AvatarProfile,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="user_preferences",
    )
    speed = models.CharField(max_length=8, choices=SPEED_CHOICES, default="normal")
    pitch = models.CharField(max_length=8, choices=PITCH_CHOICES, default="normal")
    sound_effects_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User AI preference")
        verbose_name_plural = _("User AI preferences")

    def __str__(self):
        return f"prefs<{self.user_id}>"


class LibraryAudioSession(models.Model):
    """One natural-reader session for a library chapter.

    Mirrors AITutorSession: opened before TTS, closed when the listener
    pauses / finishes, and deducts seconds from the library audio quota
    bucket. The partial unique constraint forbids two parallel listening
    sessions per user.
    """

    STATUS_CHOICES = [
        ("in_progress", _("In progress")),
        ("completed", _("Completed")),
        ("cancelled", _("Cancelled")),
        ("killed_quota_exceeded", _("Stopped — quota exceeded")),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="library_audio_sessions",
    )
    # We point at the library.Chapter via a soft FK (positive int) to keep
    # subscriptions from depending on the library app at import time.
    chapter_id = models.PositiveIntegerField(db_index=True)
    chapter_title = models.CharField(max_length=200, blank=True)
    voice_profile = models.ForeignKey(
        "subscriptions.VoiceProfile",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="library_audio_sessions",
    )
    status = models.CharField(
        max_length=32, choices=STATUS_CHOICES,
        default="in_progress", db_index=True,
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    consumed_seconds = models.PositiveIntegerField(default=0)
    remaining_after_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "-started_at"]),
            models.Index(fields=["status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user"], condition=models.Q(status="in_progress"),
                name="unique_in_progress_library_audio_per_user",
            ),
        ]
        verbose_name = _("Library audio session")
        verbose_name_plural = _("Library audio sessions")

    def __str__(self):
        return f"libaudio<{self.pk}> user={self.user_id} status={self.status}"


class TextNormalizationLog(models.Model):
    """Audit row capturing what the natural reader changed.

    The user spec asks us to keep both versions so reviewers can spot
    quality regressions (e.g. an abbreviation expanding to garbage). We
    don't store one row per character — only one row per *render call*,
    so a chapter that's read 100 times yields up to 100 rows. Run
    ``./manage.py shell`` to inspect a row's ``diff_summary``.
    """

    SOURCE_CHOICES = [
        ("library_chapter", _("Library chapter")),
        ("tutor_message", _("Tutor message")),
        ("ad_hoc", _("Ad hoc")),
    ]

    source = models.CharField(max_length=32, choices=SOURCE_CHOICES, default="library_chapter")
    source_id = models.PositiveIntegerField(
        null=True, blank=True,
        help_text=_("Chapter ID, TutorMessage ID, etc."),
    )
    language = models.CharField(max_length=8, default="en")
    original_text = models.TextField()
    tts_ready_text = models.TextField()
    applied_rules = models.JSONField(default=list, blank=True)
    original_chars = models.PositiveIntegerField(default=0)
    tts_chars = models.PositiveIntegerField(default=0)
    estimated_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["source", "source_id", "-created_at"]),
        ]
        verbose_name = _("Text normalization log")
        verbose_name_plural = _("Text normalization logs")

    def __str__(self):
        return f"norm<{self.pk}> {self.source}:{self.source_id}"


class UserDailyQuota(models.Model):
    """Per-day counter of AI-Tutor + library-audio seconds consumed.

    One row per (user, date). Persisting in DB (vs cache) means:
      * we keep an audit trail of historical usage
      * we don't lose state on a cache flush / redeploy
      * we can show admins a precise consumption breakdown
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_quotas",
    )
    date = models.DateField(db_index=True)
    ai_tutor_seconds_used = models.PositiveIntegerField(default=0)
    library_seconds_used = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="unique_user_daily_quota",
            ),
        ]
        verbose_name = _("User daily quota")
        verbose_name_plural = _("User daily quotas")

    def __str__(self):
        return f"{self.user_id} @ {self.date}: {self.ai_tutor_seconds_used}s tutor"
