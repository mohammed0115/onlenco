from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class QuestionFactoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "question_factory"
    verbose_name = _("Question Factory (Blueprint-driven)")
