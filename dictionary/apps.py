from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class DictionaryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dictionary"
    verbose_name = _("Dictionary")

