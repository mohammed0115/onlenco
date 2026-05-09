from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ClubConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "club"
    verbose_name = _("Club")

