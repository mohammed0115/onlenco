from django.conf import settings
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.utils import translation
from django.urls import reverse
from django.views.decorators.http import require_http_methods


def home(request):
    """Public landing page. Server-renders the hero, features grid,
    CEFR ladder, and pricing tiers.

    Pricing is read from the ``SubscriptionPlan`` table so an admin can
    edit prices / names / which plan is featured from the Control Center
    (Plans page) — nothing on the pricing section is hardcoded.
    """
    from subscriptions.models import SubscriptionPlan

    levels = ["A0", "A1", "A2", "B1", "B2", "C1", "C2"]
    features = [
        ("brain",   "feat.placement.t", "feat.placement.d"),
        ("mic",     "feat.tutor.t",     "feat.tutor.d"),
        ("book",    "feat.lessons.t",   "feat.lessons.d"),
        ("users",   "feat.club.t",      "feat.club.d"),
        ("library", "feat.library.t",   "feat.library.d"),
        ("wallet",  "feat.pay.t",       "feat.pay.d"),
    ]
    plans = (
        SubscriptionPlan.objects
        .filter(is_active=True, is_free_trial=False)
        .order_by("sort_order", "price_sdg")
    )
    return render(request, "core/home.html", {
        "levels": levels,
        "features": features,
        "plans": plans,
    })


def not_found(request, exception=None):
    return render(request, "core/404.html", status=404)


@require_http_methods(["GET", "POST"])
def set_language(request):
    """Switches the active language and persists it.

    Mirrors Django's built-in `i18n.set_language` view but is a tad
    simpler and also saves the choice on the user's Profile so it sticks
    across devices.
    """
    # Default fallback is Arabic — matches `settings.LANGUAGE_CODE` and
    # the project's primary audience. Anonymous flow users with no
    # profile yet still land in AR.
    lang = request.POST.get("language") or request.GET.get("lang") or "ar"
    if lang not in dict(settings.LANGUAGES):
        lang = "ar"

    translation.activate(lang)
    request.session["django_language"] = lang

    if request.user.is_authenticated and hasattr(request.user, "profile"):
        request.user.profile.preferred_language = lang
        request.user.profile.save(update_fields=["preferred_language"])

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER") or reverse("home")
    response = HttpResponseRedirect(next_url)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        lang,
        max_age=getattr(settings, "LANGUAGE_COOKIE_AGE", None),
        path=getattr(settings, "LANGUAGE_COOKIE_PATH", "/"),
        domain=getattr(settings, "LANGUAGE_COOKIE_DOMAIN", None),
        secure=getattr(settings, "LANGUAGE_COOKIE_SECURE", False),
        httponly=getattr(settings, "LANGUAGE_COOKIE_HTTPONLY", False),
        samesite=getattr(settings, "LANGUAGE_COOKIE_SAMESITE", "Lax"),
    )
    return response
