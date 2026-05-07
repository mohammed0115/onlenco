from functools import wraps

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        profile = getattr(request.user, "profile", None)
        if not profile or not profile.is_admin:
            return HttpResponseForbidden("Forbidden")
        return view_func(request, *args, **kwargs)

    return _wrapped

