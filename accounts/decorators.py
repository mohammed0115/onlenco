"""Shared access-control decorators.

`subscription_required` centralises the paywall check that was
previously duplicated across `lessons.views`, `tutor.views`,
`library.views`, etc. New premium views should always go through this
decorator instead of inline `profile.is_subscribed` checks.

A free user (no active subscription) is allowed past the gate when the
view explicitly enables the free-tier trial — i.e. the first lesson /
first attempt the student ever takes. The default trial is encoded in
`Profile.is_in_free_tier` so the per-view decision is one bit, not
duplicated business logic.
"""
from __future__ import annotations

from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse


def subscription_required(*, allow_free_tier: bool = False, soft_redirect: bool = True):
    """Gate a view on `request.user.profile.is_subscribed`.

    Args:
      allow_free_tier: when True, also let users through if
        `profile.is_in_free_tier` is True. Used for the first beginner
        lesson and the first placement-driven personalised exercise so
        a brand-new free user actually reaches the learning loop.
      soft_redirect: when True, send unauthenticated/unsubscribed users
        to /subscribe/ instead of 403. Keep False on API endpoints.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request.user, "profile", None)
            if profile is None:
                return HttpResponseForbidden("Profile required")
            if profile.is_subscribed:
                return view_func(request, *args, **kwargs)
            if allow_free_tier and profile.is_in_free_tier:
                return view_func(request, *args, **kwargs)
            if soft_redirect:
                try:
                    return redirect(reverse("subscribe"))
                except NoReverseMatch:
                    pass
            return HttpResponseForbidden("Subscription required")
        return _wrapped
    return decorator
