from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AIEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_engine"
    verbose_name = _("AI Engine (Model Router)")
