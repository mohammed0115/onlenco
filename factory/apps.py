from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class FactoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "factory"
    verbose_name = _("Question Factory")
