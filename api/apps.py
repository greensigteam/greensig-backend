from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        print("[APP] ========== ApiConfig.ready() APPELE ==========")

        try:
            from django.db.models.signals import pre_save, post_save, post_delete
            from api.models import (
                Site, SousSite,
                Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
                Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon,
            )
            from api.signals import (
                site_pre_save, site_post_save,
                invalidate_gis_object_cache, invalidate_site_cache,
            )

            # Signals existants — notifications superviseur
            pre_save.connect(site_pre_save, sender=Site)
            post_save.connect(site_post_save, sender=Site)

            # Invalidation du cache — Sites & SousSites
            for model in [Site, SousSite]:
                post_save.connect(invalidate_site_cache, sender=model)
                post_delete.connect(invalidate_site_cache, sender=model)

            # Invalidation du cache — 15 types d'objets GIS
            gis_models = [
                Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
                Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon,
            ]
            for model in gis_models:
                post_save.connect(invalidate_gis_object_cache, sender=model)
                post_delete.connect(invalidate_gis_object_cache, sender=model)

            print("[APP] Signals + cache invalidation connectes")
        except Exception as e:
            print(f"[APP] ERREUR lors de la connexion des signals: {e}")
            import traceback
            traceback.print_exc()


default_app_config = 'api.apps.ApiConfig'
