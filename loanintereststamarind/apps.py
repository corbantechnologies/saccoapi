from django.apps import AppConfig


class LoanintereststamarindConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loanintereststamarind'

    def ready(self):
        import loanintereststamarind.signals
