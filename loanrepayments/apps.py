from django.apps import AppConfig


class LoanrepaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loanrepayments'

    def ready(self):
        import loanrepayments.signals
