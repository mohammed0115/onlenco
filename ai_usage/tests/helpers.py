"""Shared test fixtures / fakes for ai_usage tests."""
from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.utils import timezone


def make_user(username="stu", **profile_kwargs):
    user = get_user_model().objects.create_user(username=username, password="pw12345!")
    if profile_kwargs:
        profile = user.profile
        for k, v in profile_kwargs.items():
            setattr(profile, k, v)
        profile.save()
    return user


def give_plan(user, minutes, code=None):
    """Attach an active subscription granting ``minutes`` AI-Tutor minutes/day."""
    from subscriptions.models import SubscriptionPlan, UserSubscription
    code = code or f"plan{minutes}"
    plan, _ = SubscriptionPlan.objects.get_or_create(
        code=code,
        defaults=dict(name_en=f"{minutes}m", name_ar=f"{minutes}د",
                      ai_tutor_daily_minutes=minutes),
    )
    UserSubscription.objects.create(
        user=user, plan=plan, status="active", start_date=timezone.now(),
    )
    return plan


class FakeResponse:
    """Minimal stand-in for a ``requests`` Response."""

    def __init__(self, *, json_data=None, content=b"", lines=None, status_code=200):
        self._json = json_data or {}
        self.content = content
        self._lines = lines or []
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._json

    def iter_lines(self, decode_unicode=True):
        for line in self._lines:
            yield line


def chat_json(content="hello", prompt_tokens=100, completion_tokens=50):
    return {
        "choices": [{"message": {"content": content}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def sse_lines(tokens=("He", "llo"), prompt_tokens=10, completion_tokens=2, with_usage=True):
    lines = []
    for t in tokens:
        lines.append("data: " + json.dumps({"choices": [{"delta": {"content": t}}]}))
    if with_usage:
        lines.append("data: " + json.dumps({
            "choices": [{"delta": {}}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
        }))
    lines.append("data: [DONE]")
    return lines
