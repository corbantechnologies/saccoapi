from django.apps import AppConfig


class FeespaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'feespayments'

    def ready(self):
        import feespayments.signals
