from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        print("[APP] ========== ApiConfig.ready() APPELE ==========")

        try:
            # Importer les signals et les connecter manuellement
            from django.db.models.signals import pre_save, post_save
            from api.models import Site
            from api.signals import site_pre_save, site_post_save

            # Connecter les signals au modele Site
            pre_save.connect(site_pre_save, sender=Site)
            post_save.connect(site_post_save, sender=Site)

            print(f"[APP] Signals connectes pour Site: {Site}")
            print("[APP] ========== Signals Site connectes ==========")
        except Exception as e:
            print(f"[APP] ERREUR lors de la connexion des signals: {e}")
            import traceback
            traceback.print_exc()


default_app_config = 'api.apps.ApiConfig'
