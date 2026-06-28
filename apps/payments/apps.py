from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"
    verbose_name = "المالية والمدفوعات"

    def ready(self):
        from . import finance_signals  # noqa
