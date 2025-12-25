from django.apps import AppConfig

class ApiPlanificationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api_planification'

    def ready(self):
        """Import signals when Django starts"""
        import api_planification.signals  # noqa
