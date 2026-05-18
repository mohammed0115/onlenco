from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from . import constants as C


LANGUAGE_CHOICES = [("en", _("English")), ("ar", _("Arabic"))]


class LearnerActivitySnapshot(models.Model):
    """Per-day rollup of all learning activity for one user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activity_snapshots",
    )
    date = models.DateField()

    # Tutor / speaking
    speaking_minutes = models.PositiveIntegerField(default=0)
    ai_chat_minutes = models.PositiveIntegerField(default=0)
    ai_messages_count = models.PositiveIntegerField(default=0)
    listening_minutes = models.PositiveIntegerField(default=0)

    # Reading
    reading_minutes = models.PositiveIntegerField(default=0)
    words_read = models.PositiveIntegerField(default=0)

    # Lessons + quizzes
    lessons_completed = models.PositiveIntegerField(default=0)
    quizzes_completed = models.PositiveIntegerField(default=0)
    questions_answered = models.PositiveIntegerField(default=0)
    correct_answers = models.PositiveIntegerField(default=0)
    quiz_accuracy = models.FloatField(default=0.0)

    # Vocabulary / writing
    vocabulary_words_learned = models.PositiveIntegerField(default=0)
    writing_attempts = models.PositiveIntegerField(default=0)

    # Assessments
    weekly_assessments_completed = models.PositiveIntegerField(default=0)

    # Streak / level
    current_streak_days = models.PositiveIntegerField(default=0)
    inactive_days = models.PositiveIntegerField(default=0)
    cefr_level = models.CharField(max_length=2, blank=True)
    theta_score = models.FloatField(default=0.0)
    mastery_delta = models.FloatField(default=0.0)

    # Behavioral analytics scores (0-100). Computed by the risk_engine
    # nightly and surfaced on the academic-admin "at-risk students" view.
    engagement_score = models.FloatField(default=0.0, db_index=True)
    churn_risk_score = models.FloatField(default=0.0, db_index=True)

    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"], name="motivation_unique_user_date"
            )
        ]
        indexes = [
            models.Index(fields=["user", "-date"]),
            models.Index(fields=["date"]),
        ]
        verbose_name = _("Learner activity snapshot")
        verbose_name_plural = _("Learner activity snapshots")

    def __str__(self):
        return f"Snapshot<{self.user_id}> {self.date}"


class Achievement(models.Model):
    """Catalog of reusable achievements (seeded once, then awarded on the fly)."""

    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    name_ar = models.CharField(max_length=120, blank=True)
    description_ar = models.TextField(blank=True)
    category = models.CharField(
        max_length=20, choices=C.ACHIEVEMENT_CATEGORY_CHOICES
    )
    threshold_value = models.IntegerField(default=0)
    xp_reward = models.PositiveIntegerField(default=0)
    badge_icon = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["category", "threshold_value", "name"]
        verbose_name = _("Achievement")
        verbose_name_plural = _("Achievements")

    def __str__(self):
        return f"{self.code} ({self.category})"


class UserAchievement(models.Model):
    """One row per (user, achievement) once earned."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements_earned",
    )
    achievement = models.ForeignKey(
        Achievement, on_delete=models.CASCADE, related_name="earners"
    )
    earned_at = models.DateTimeField(auto_now_add=True)
    source_snapshot = models.ForeignKey(
        LearnerActivitySnapshot,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="achievements_unlocked",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-earned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "achievement"], name="motivation_unique_user_achievement"
            )
        ]
        verbose_name = _("User achievement")
        verbose_name_plural = _("User achievements")

    def __str__(self):
        return f"{self.user_id} ⇒ {self.achievement.code}"


class UserXP(models.Model):
    """Aggregate XP totals; one row per user."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="xp",
    )
    total_xp = models.PositiveIntegerField(default=0)
    weekly_xp = models.PositiveIntegerField(default=0)
    monthly_xp = models.PositiveIntegerField(default=0)
    level_number = models.PositiveIntegerField(default=1)
    weekly_xp_reset_at = models.DateField(null=True, blank=True)
    monthly_xp_reset_at = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User XP")
        verbose_name_plural = _("User XP")

    def __str__(self):
        return f"XP<{self.user_id}> total={self.total_xp} lvl={self.level_number}"


class UserBadge(models.Model):
    """Badges awarded to users (separate from achievements; smaller, decorative)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="badges_earned",
    )
    badge_code = models.CharField(max_length=80)
    badge_name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    earned_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-earned_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "badge_code"], name="motivation_unique_user_badge"
            )
        ]
        verbose_name = _("User badge")
        verbose_name_plural = _("User badges")

    def __str__(self):
        return f"Badge<{self.user_id}> {self.badge_code}"


class MotivationMessage(models.Model):
    """A generated motivation message — surfaced in-app, optionally emailed."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="motivation_messages",
    )
    message_type = models.CharField(max_length=20, choices=C.MESSAGE_TYPE_CHOICES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="en")
    tone = models.CharField(max_length=20, choices=C.TONE_CHOICES, default=C.TONE_SUPPORTIVE)

    related_activity = models.CharField(max_length=40, blank=True)
    related_achievement = models.ForeignKey(
        Achievement,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="related_messages",
    )
    related_snapshot = models.ForeignKey(
        LearnerActivitySnapshot,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="related_messages",
    )

    status = models.CharField(
        max_length=15, choices=C.STATUS_CHOICES, default=C.STATUS_GENERATED
    )
    sent_via = models.CharField(
        max_length=10, choices=C.SENT_VIA_CHOICES, default=C.VIA_NONE
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["message_type"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = _("Motivation message")
        verbose_name_plural = _("Motivation messages")

    def __str__(self):
        return f"Mot<{self.user_id}> {self.message_type} {self.status}"


class Challenge(models.Model):
    """A time-boxed goal users opt into to earn bonus XP.

    `kind` is one of daily/weekly/monthly. `metric` names a snapshot
    field — when the engine ticks, current value is read off the user's
    daily snapshots within [start_at, end_at]. Once the cumulative value
    crosses `target_value`, the challenge is marked complete and the
    `xp_reward` is credited via `xp_service.award_xp`.
    """

    KIND_CHOICES = [("daily", "Daily"), ("weekly", "Weekly"), ("monthly", "Monthly")]
    METRIC_CHOICES = [
        ("lessons_completed",      "Lessons completed"),
        ("questions_answered",     "Questions answered"),
        ("ai_chat_minutes",        "AI tutor minutes"),
        ("speaking_minutes",       "Speaking minutes"),
        ("words_read",             "Words read"),
        ("vocabulary_words_learned", "Vocabulary words"),
        ("writing_attempts",       "Writing attempts"),
    ]

    code = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=120)
    title_ar = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    description_ar = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    metric = models.CharField(max_length=40, choices=METRIC_CHOICES)
    target_value = models.PositiveIntegerField()
    xp_reward = models.PositiveIntegerField(default=50)
    start_at = models.DateField()
    end_at = models.DateField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_at"]
        indexes = [models.Index(fields=["kind", "is_active", "start_at"])]
        verbose_name = _("Challenge")
        verbose_name_plural = _("Challenges")

    def __str__(self):
        return f"{self.kind}:{self.code} ({self.metric}≥{self.target_value})"


class ChallengeProgress(models.Model):
    """Per-user progress on a Challenge."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenge_progress",
    )
    challenge = models.ForeignKey(
        Challenge, on_delete=models.CASCADE, related_name="participants",
    )
    current_value = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "challenge"], name="motivation_unique_user_challenge"
            )
        ]
        indexes = [models.Index(fields=["user", "-updated_at"])]
        verbose_name = _("Challenge progress")
        verbose_name_plural = _("Challenge progress")

    def __str__(self):
        return f"ChalProg<{self.user_id}> {self.challenge.code} {self.current_value}/{self.challenge.target_value}"


class LeaderboardEntry(models.Model):
    """Denormalised weekly/monthly leaderboard row.

    Rebuilt nightly by the leaderboard service so per-request views can
    do a single ordered query instead of aggregating UserXP + snapshots.
    Privacy-aware: only users whose `MotivationPreference.show_on_leaderboard`
    is True are written.
    """

    PERIOD_CHOICES = [("weekly", "Weekly"), ("monthly", "Monthly")]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leaderboard_entries",
    )
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    xp = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)
    display_name = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["period", "-period_start", "rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "period", "period_start"],
                name="motivation_unique_leaderboard_period",
            )
        ]
        indexes = [
            models.Index(fields=["period", "-period_start", "rank"]),
        ]
        verbose_name = _("Leaderboard entry")
        verbose_name_plural = _("Leaderboard entries")

    def __str__(self):
        return f"LB<{self.period}:{self.period_start}> #{self.rank} u={self.user_id} xp={self.xp}"


class MotivationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="motivation_preference",
    )
    enable_motivation_notifications = models.BooleanField(default=True)
    enable_email_motivation = models.BooleanField(default=True)
    enable_streak_reminders = models.BooleanField(default=True)
    enable_weekly_summary = models.BooleanField(default=True)
    show_on_leaderboard = models.BooleanField(default=True)
    preferred_tone = models.CharField(
        max_length=20, choices=C.TONE_CHOICES, default=C.TONE_SUPPORTIVE
    )
    motivation_frequency = models.CharField(
        max_length=10, choices=C.FREQUENCY_CHOICES, default=C.FREQ_NORMAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Motivation preference")
        verbose_name_plural = _("Motivation preferences")

    def __str__(self):
        return f"MotPref<{self.user_id}> tone={self.preferred_tone}"


# ---------------------------------------------------------------------------
# Gamification audio (Sprint 5)
# ---------------------------------------------------------------------------

class GameEventSound(models.Model):
    """A catalog of audio cues + animations shown when the learner achieves
    something. One row per event code (e.g. ``success``, ``level_up``).

    Admins edit ``audio_url`` / messages / animation from the Control
    Center; the frontend polls ``/api/v1/motivation/recent-rewards/``
    on each page load and plays whatever sounds correspond to events
    earned in the last 60 seconds.

    Honouring per-user mute: the user's
    ``subscriptions.UserAIPreference.sound_effects_enabled`` flag is
    consulted by ``sound_service.event_sounds_for_user`` — disabled
    users still see the toast / XP popup, just without audio.
    """

    EVENT_CHOICES = [
        ("success", _("Success — lesson / quiz completed")),
        ("level_up", _("Level up")),
        ("bonus", _("XP bonus")),
        ("streak", _("Streak milestone")),
        ("achievement_unlocked", _("Achievement unlocked")),
    ]
    ANIMATION_CHOICES = [
        ("confetti", _("Confetti burst")),
        ("sparkle", _("Sparkle")),
        ("trophy", _("Trophy pop")),
        ("flame", _("Flame streak")),
        ("rocket", _("Rocket")),
        ("none", _("None")),
    ]

    code = models.CharField(max_length=32, choices=EVENT_CHOICES, unique=True)
    audio_url = models.URLField(
        blank=True,
        help_text=_("Public URL to a short MP3/OGG (≤ 4 s)."),
    )
    fallback_audio_path = models.CharField(
        max_length=255, blank=True,
        help_text=_("Static path under STATIC_URL when audio_url is empty."),
    )
    message_en = models.CharField(max_length=160)
    message_ar = models.CharField(max_length=160)
    animation = models.CharField(
        max_length=24, choices=ANIMATION_CHOICES, default="sparkle",
    )
    xp_callout_template_en = models.CharField(
        max_length=120, blank=True,
        help_text=_("Optional callout like '+{xp} XP' shown alongside the toast."),
    )
    xp_callout_template_ar = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        verbose_name = _("Game event sound")
        verbose_name_plural = _("Game event sounds")

    def __str__(self):
        return f"{self.get_code_display()}"

    @property
    def effective_audio_src(self) -> str:
        """Return the URL or the static fallback path."""
        return self.audio_url or self.fallback_audio_path
