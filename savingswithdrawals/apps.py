from django.apps import AppConfig


class SavingswithdrawalsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'savingswithdrawals'

    def ready(self):
        import savingswithdrawals.signals
