"""URL configuration for the Onlenco project."""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from core.views import set_language

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
    path("admin-analytics/", include("analytics.urls")),
    path("api/v1/", include("api.v1.urls")),
    path("notifications/", include("notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
