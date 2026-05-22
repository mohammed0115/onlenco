from django.conf import settings
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.utils import translation
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .seo_content import get_seo_page


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


def _active_lang() -> str:
    """Normalise the active language to ``"ar"`` / ``"en"``."""
    lang = translation.get_language() or "en"
    return "ar" if lang.startswith("ar") else "en"


def robots_txt(request):
    """Serve ``/robots.txt``.

    Allows the whole public site, points crawlers at the sitemap, and
    keeps them out of the login-gated admin / API areas so crawl budget
    is not spent on pages that only redirect to the sign-in screen.
    """
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /django-admin/",
        "Disallow: /admin/",
        "Disallow: /control/",
        "Disallow: /teacher/",
        "Disallow: /api/",
        "Disallow: /set-language/",
        "",
        f"Sitemap: {site_url}/sitemap.xml",
        "",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def seo_landing(request, key: str):
    """Render a public SEO landing page from :mod:`core.seo_content`.

    These pages are deliberately *not* login-gated — they exist so the
    platform is indexable for its target keywords. The pricing page also
    renders the live ``SubscriptionPlan`` rows.

    Bilingual strings are resolved to the active language here so the
    template stays simple, and a JSON-LD ``FAQPage`` is built for the
    page's questions.
    """
    import json

    from django.utils.safestring import mark_safe

    page = get_seo_page(key)
    if page is None:
        raise Http404("Unknown SEO page")

    lang = _active_lang()
    localised = {
        "key": page["key"],
        "h1": page["h1"][lang],
        "intro": page["intro"][lang],
        "sections": [
            {
                "icon": s["icon"],
                "title": s["title"][lang],
                "body": s["body"][lang],
            }
            for s in page["sections"]
        ],
        "faq": [
            {"q": f["q"][lang], "a": f["a"][lang]}
            for f in page["faq"]
        ],
        "show_plans": page.get("show_plans", False),
    }

    faq_ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["q"],
                "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
            }
            for item in localised["faq"]
        ],
    }

    context = {
        "page": localised,
        "seo_title": page["seo_title"][lang],
        "seo_description": page["seo_description"][lang],
        "faq_jsonld": mark_safe(json.dumps(faq_ld, ensure_ascii=False)),
    }
    if page.get("show_plans"):
        from subscriptions.models import SubscriptionPlan
        context["plans"] = (
            SubscriptionPlan.objects
            .filter(is_active=True, is_free_trial=False)
            .order_by("sort_order", "price_sdg")
        )
    return render(request, "core/seo_landing.html", context)


# Thin named wrappers — one per public SEO URL so `reverse()` and the
# sitemap can address each page individually.
def seo_pricing(request):
    return seo_landing(request, "pricing")


def seo_placement_test(request):
    return seo_landing(request, "placement-test")


def seo_ai_english_tutor(request):
    return seo_landing(request, "ai-english-tutor")


def seo_english_for_beginners(request):
    return seo_landing(request, "english-for-beginners")


def seo_english_speaking_practice(request):
    return seo_landing(request, "english-speaking-practice")


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
