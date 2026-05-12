"""Small helpers used across the daily_learning test suite."""
from __future__ import annotations

from django.contrib.auth import get_user_model

User = get_user_model()


def make_student(
    *,
    username: str,
    cefr_level: str = "A1",
    language: str = "en",
    onboarding_path: str = "placement_test",
    onboarding_completed: bool = True,
):
    """Create a User + populated Profile in one call.

    Profile is auto-created by signal in accounts.models, we just edit it.
    """
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.test",
        password="x12345",
    )
    profile = user.profile
    profile.cefr_level = cefr_level
    profile.preferred_language = language
    profile.onboarding_path = onboarding_path
    profile.onboarding_completed = onboarding_completed
    profile.save()
    return user
