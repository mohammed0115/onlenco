from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PlatformAdminConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "platform_admin"
    verbose_name = _("Onlenco Control Center")

