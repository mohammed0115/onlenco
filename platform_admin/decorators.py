from __future__ import annotations

from functools import wraps

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from . import permissions


def control_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
        if not permissions.is_control_user(request.user):
            return HttpResponseForbidden("Forbidden")
        return view_func(request, *args, **kwargs)
    return _wrapped


def control_permission_required(capability: str):
    def decorator(view_func):
        @wraps(view_func)
        @control_login_required
        def _wrapped(request, *args, **kwargs):
            if not permissions.has_capability(request.user, capability):
                return HttpResponseForbidden("Forbidden")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def mutation_permission_required(capability: str):
    def decorator(view_func):
        @wraps(view_func)
        @control_login_required
        def _wrapped(request, *args, **kwargs):
            if not permissions.can_mutate(request.user, capability):
                return HttpResponseForbidden("Forbidden")
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
