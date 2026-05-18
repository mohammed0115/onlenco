from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "subscriptions"
    verbose_name = "Subscriptions & Plans"

    def ready(self):
        # Wire signals (free-trial grant on user signup).
        from . import signals  # noqa: F401
