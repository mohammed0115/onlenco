"""URL configuration for the Onlenco project."""
from django import forms
from django.contrib import admin
from django.contrib.admin.forms import AdminAuthenticationForm
from django.urls import include, path
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
    path("admin/", admin.site.urls),
    path("set-language/", set_language, name="set_language"),

    path("", include("core.urls")),
    path("auth/", include("accounts.urls")),
    path("dashboard/", include("lessons.urls")),
    path("placement/", include("placement.urls")),
    path("payments/", include("payments.urls")),
    path("tutor/", include("tutor.urls")),
    path("library/", include("library.urls")),
    path("dictionary/", include("dictionary.urls")),
    path("club/", include("club.urls")),
    path("exams/", include("exams.urls")),
    path("admin-analytics/", include("analytics.urls")),
    path("api/v1/", include("api.v1.urls")),
    path("notifications/", include("notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
