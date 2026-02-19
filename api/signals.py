"""
Signals pour l'application API (Sites, Objets GIS, etc.)

Ces signals sont connectes manuellement dans apps.py pour eviter les problemes
avec les decorateurs @receiver et les string senders.

Invalidation du cache :
  - Site / SousSite → STATISTICS, FILTERS, REPORTING
  - Objets GIS (15 types) → STATISTICS, FILTERS
"""

import logging

logger = logging.getLogger(__name__)

print("[SIGNALS] ========== api/signals.py CHARGE ==========")


# ==============================================================================
# INVALIDATION DU CACHE APRÈS MUTATIONS GIS
# ==============================================================================

def invalidate_gis_object_cache(sender, instance, **kwargs):
    """Invalide les caches STATISTICS + FILTERS après mutation d'un objet GIS."""
    from greensig_web.cache_utils import invalidate_on_gis_object_mutation
    invalidate_on_gis_object_mutation()


def invalidate_site_cache(sender, instance, **kwargs):
    """Invalide les caches STATISTICS + FILTERS + REPORTING après mutation d'un Site/SousSite."""
    from greensig_web.cache_utils import invalidate_on_site_mutation
    invalidate_on_site_mutation()


def site_pre_save(sender, instance, **kwargs):
    """
    Capture l'ancien superviseur avant la sauvegarde pour detecter les changements.
    """
    print(f"[SIGNAL-DEBUG] pre_save Site #{instance.pk} - superviseur actuel: {instance.superviseur_id}")

    if instance.pk:
        try:
            old_instance = sender.objects.get(pk=instance.pk)
            instance._old_superviseur_id = old_instance.superviseur_id
            print(f"[SIGNAL-DEBUG] Site #{instance.pk} - ancien superviseur: {old_instance.superviseur_id}")
        except sender.DoesNotExist:
            instance._old_superviseur_id = None
            print(f"[SIGNAL-DEBUG] Site #{instance.pk} - instance non trouvee en base")
    else:
        instance._old_superviseur_id = None
        print(f"[SIGNAL-DEBUG] Nouveau site (pas de pk)")


def site_post_save(sender, instance, created, **kwargs):
    """
    Notifier les superviseurs lors de l'assignation/desassignation de sites.

    - Si un nouveau superviseur est assigne: notifier le nouveau superviseur
    - Si le superviseur change: notifier l'ancien (retire) et le nouveau (assigne)
    - Si le superviseur est retire: notifier l'ancien superviseur
    """
    from api.services.notifications import NotificationService
    from api_users.models import Superviseur

    old_superviseur_id = getattr(instance, '_old_superviseur_id', None)
    new_superviseur_id = instance.superviseur_id

    print(f"[SIGNAL-DEBUG] post_save Site #{instance.id} - created={created}")
    print(f"[SIGNAL-DEBUG] old_superviseur_id={old_superviseur_id}, new_superviseur_id={new_superviseur_id}")

    # Pas de changement
    if old_superviseur_id == new_superviseur_id:
        print(f"[SIGNAL-DEBUG] Pas de changement de superviseur - skip")
        return

    # Recuperer l'acteur (utilisateur qui a fait la modification)
    acteur = None

    # Ancien superviseur perd le site
    if old_superviseur_id and old_superviseur_id != new_superviseur_id:
        try:
            old_superviseur = Superviseur.objects.select_related('utilisateur').get(pk=old_superviseur_id)
            print(f"[SIGNAL] Envoi notification site_retire a {old_superviseur.utilisateur.email if old_superviseur.utilisateur else 'N/A'}")
            NotificationService.notify_site_retire(instance, old_superviseur, acteur=acteur)
            print(f"[SIGNAL] Site #{instance.id} retire du superviseur #{old_superviseur_id}")
        except Superviseur.DoesNotExist:
            print(f"[SIGNAL] Superviseur #{old_superviseur_id} non trouve")
        except Exception as e:
            print(f"[SIGNAL] ERREUR notify_site_retire: {e}")

    # Nouveau superviseur recoit le site
    if new_superviseur_id:
        try:
            new_superviseur = Superviseur.objects.select_related('utilisateur').get(pk=new_superviseur_id)
            print(f"[SIGNAL] Envoi notification site_assigne a {new_superviseur.utilisateur.email if new_superviseur.utilisateur else 'N/A'}")
            NotificationService.notify_site_assigne(instance, new_superviseur, acteur=acteur)
            print(f"[SIGNAL] Site #{instance.id} assigne au superviseur #{new_superviseur_id}")
        except Superviseur.DoesNotExist:
            print(f"[SIGNAL] Superviseur #{new_superviseur_id} non trouve")
        except Exception as e:
            print(f"[SIGNAL] ERREUR notify_site_assigne: {e}")
