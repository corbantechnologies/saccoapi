from django.apps import AppConfig


class MemberfeesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'memberfees'

    def ready(self):
        import memberfees.signals
