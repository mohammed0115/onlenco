"""Onboarding helpers — single source of truth for the new-user flow.

Why this lives in `accounts`:
  * The `Profile` carries the four onboarding fields.
  * The login redirect rule is consulted from `auth_view`, the dashboard,
    and the redirect middleware — keeping the rule in one function means
    none of those drift out of sync.

Public surface:
    needs_onboarding(profile) -> bool
    next_url_for(user) -> str | None
    complete_beginner_onboarding(user) -> Profile
    complete_placement_onboarding(profile, level: str) -> None
"""
from __future__ import annotations

import logging
from typing import Any

from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_BEGINNER_LEVEL = "A0"


# ---------------------------------------------------------------------------
# Decision rule
# ---------------------------------------------------------------------------

def needs_onboarding(profile) -> bool:
    """True if the student should land on the onboarding choice page next.

    Admin-reset works through this same field — admins flip
    `onboarding_completed=False` and the user goes through the choice
    again on their next login."""
    if profile is None:
        return False
    return not bool(profile.onboarding_completed)


def next_url_for(user) -> str | None:
    """Return the URL the user should be on next, or None if the
    current page is fine.

    Order of precedence:
      1. Email not verified → verify_email_otp
      2. Onboarding not done → onboarding_choice
      3. None (continue to dashboard / requested page)
    """
    if not getattr(user, "is_authenticated", False):
        return None
    profile = getattr(user, "profile", None)
    if profile is None:
        return None
    if not profile.email_verified:
        # The verify_email_otp page already exists; we honour its precedence.
        try:
            return reverse("verify_email_otp")
        except Exception:
            return None
    if needs_onboarding(profile):
        try:
            return reverse("onboarding_choice")
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Path completion helpers
# ---------------------------------------------------------------------------

def complete_placement_onboarding(profile, *, level: str) -> None:
    """Mark the user's onboarding as completed via the placement path.

    Called from `placement.views.placement` after a successful AI grade.
    Idempotent — safe to call on a user who's already onboarded (e.g.
    a retake)."""
    profile.onboarding_completed = True
    profile.onboarding_path = "placement_test"
    if not profile.initial_cefr_level:
        profile.initial_cefr_level = level
    if not profile.onboarding_completed_at:
        profile.onboarding_completed_at = timezone.now()
    profile.save(update_fields=[
        "onboarding_completed", "onboarding_path",
        "initial_cefr_level", "onboarding_completed_at",
    ])


def complete_beginner_onboarding(user) -> Any:
    """Set up a brand-new beginner: A0 level, learning profile,
    minimal recommendations. Idempotent.

    Returns the user's profile. Best-effort on the side-effects — the
    onboarding flag is the contract; everything else is opportunistic
    and never blocks the redirect."""
    profile = user.profile
    if not profile.cefr_level:
        profile.cefr_level = DEFAULT_BEGINNER_LEVEL
    if not profile.initial_cefr_level:
        profile.initial_cefr_level = DEFAULT_BEGINNER_LEVEL
    profile.onboarding_completed = True
    profile.onboarding_path = "beginner_start"
    if not profile.onboarding_completed_at:
        profile.onboarding_completed_at = timezone.now()
    profile.save(update_fields=[
        "cefr_level", "initial_cefr_level",
        "onboarding_completed", "onboarding_path",
        "onboarding_completed_at",
    ])
    _seed_beginner_learning_profile(user)
    _seed_starter_recommendation(user)
    return profile


# ---------------------------------------------------------------------------
# Best-effort beginner-state seed
# ---------------------------------------------------------------------------

def _seed_beginner_learning_profile(user) -> None:
    """Create a `StudentLearningProfile` row at A0 if missing. Tolerates
    the learning_core app being absent or its API drifting."""
    try:
        from learning_core.models import StudentLearningProfile
    except Exception:
        return
    try:
        StudentLearningProfile.objects.get_or_create(
            user=user,
            defaults={
                "current_cefr_level": DEFAULT_BEGINNER_LEVEL,
                # theta_score 0.0 is the model default; explicit for clarity.
                "theta_score": 0.0,
            },
        )
    except Exception as e:
        logger.warning("beginner onboarding: profile seed failed: %s", e)


def _seed_starter_recommendation(user) -> None:
    """Write a single 'Start your first lesson' LearningRecommendation
    so the dashboard's recommendations widget isn't empty on day 1.

    Idempotent — only writes when the user has zero recommendations.
    Tolerates a missing learning_core app."""
    try:
        from learning_core.models import LearningRecommendation
    except Exception:
        return
    try:
        if LearningRecommendation.objects.filter(user=user).exists():
            return
        LearningRecommendation.objects.create(
            user=user,
            recommendation_type="continue_lesson",
            title="Start your first lesson",
            description=(
                "Your first beginner lesson is ready. Tap to start — "
                "we'll keep things short and simple."
            ),
            priority=100.0,
            metadata={"source": "beginner_onboarding"},
        )
    except Exception as e:
        logger.warning("beginner onboarding: starter rec seed failed: %s", e)


def first_beginner_lesson():
    """Return the first lesson a beginner should see (lowest level,
    lowest sort_order). Returns None when no lessons exist yet."""
    try:
        from lessons.models import Lesson
    except Exception:
        return None
    try:
        return (
            Lesson.objects
            .filter(level__in=[DEFAULT_BEGINNER_LEVEL, "A1"])
            .order_by("level", "sort_order", "id")
            .first()
        )
    except Exception:
        return None
