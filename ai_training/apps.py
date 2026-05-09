from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AITrainingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai_training"
    verbose_name = _("AI Training Datasets")
