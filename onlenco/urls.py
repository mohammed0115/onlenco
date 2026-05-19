"""URL configuration for the Onlenco project."""
from django import forms
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.urls import include, path
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from core.views import set_language


# --- Brand the admin site as "Onlenco" ---
# Spec (Part 1): site_header is the big banner, site_title is the
# <title> tag, index_title is the dashboard greeting.
admin.site.site_header = "Onlenco Learning Management"
admin.site.site_title = "Onlenco Admin Panel"
admin.site.index_title = "Onlenco Admin"


class OnlencoAdminLoginForm(AdminAuthenticationForm):
    """Login form labelled 'Email' instead of 'Username'.

    User accounts are created with `username == email`, so accepting an
    email here just feeds it into Django's normal username-based auth.
    """

    username = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(
            attrs={"autocomplete": "email", "autofocus": True, "placeholder": "you@onlenco.local"}
        ),
    )

    def clean_username(self):
        return (self.cleaned_data.get("username") or "").strip().lower()


admin.site.login_form = OnlencoAdminLoginForm


# Optional 2FA-gated admin. Enable with ENABLE_2FA_ADMIN=1 in env.
# When enabled, staff must register a TOTP device (e.g. via
# /admin/otp_totp/totpdevice/add/) and verify before reaching /admin/.
if getattr(settings, "ENABLE_2FA_ADMIN", False):
    from django_otp.admin import OTPAdminSite
    admin.site.__class__ = OTPAdminSite

urlpatterns = [
    # Built-in Django admin lives at /django-admin/ — the custom
    # Control Center owns /admin/. Django admin gives staff direct
    # CRUD over every model (placement questions, voice profiles,
    # avatar profiles, etc.) that the Control Center hasn't wrapped
    # in a custom view yet.
    path("django-admin/", admin.site.urls),
    path("admin/", include("platform_admin.urls")),
    path("teacher/", include("teacher_portal.urls")),
    path("set-language/", set_language, name="set_language"),

    path("", include("core.urls")),
    path("auth/", include("accounts.urls")),
    path("dashboard/", include("lessons.urls")),
    path("daily/", include("daily_learning.urls")),
    path("placement/", include("placement.urls")),
    path("payments/", include("payments.urls")),
    path("tutor/", include("tutor.urls")),
    path("library/", include("library.urls")),
    path("courses/", include("courses.urls")),
    path("dictionary/", include("dictionary.urls")),
    path("club/", include("club.urls")),
    path("exams/", include("exams.urls")),
    path("admin-analytics/", include("analytics.urls")),
    path("api/v1/", include("api.v1.urls")),
    path("notifications/", include("notifications.urls")),
    path("subscriptions/", include("subscriptions.urls")),
    path("settings/", RedirectView.as_view(pattern_name="profile", permanent=False), name="user_settings"),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Design tokens kitchen sink — Phase 2 regression fence.
    # Renders every --var defined in static/css/onlenco-tokens.css so
    # changes to the token layer are immediately visible. Wrapped in
    # the DEBUG branch so it is never reachable on production.
    from django.shortcuts import render

    def _design_tokens_view(request):
        # The spacing-bar widths are derived from the token names so
        # adding/removing a --space-N token here is a one-line change.
        spacing_tokens = [
            ("--space-1",  "4px"),
            ("--space-2",  "8px"),
            ("--space-3",  "12px"),
            ("--space-4",  "16px"),
            ("--space-5",  "20px"),
            ("--space-6",  "24px"),
            ("--space-7",  "28px"),
            ("--space-8",  "32px"),
            ("--space-10", "40px"),
            ("--space-12", "48px"),
            ("--space-16", "64px"),
            ("--space-20", "80px"),
        ]
        return render(request, "dev/tokens.html", {"spacing_tokens": spacing_tokens})

    urlpatterns += [path("dev/tokens/", _design_tokens_view, name="dev_design_tokens")]
