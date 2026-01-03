"""
Signals pour le module Réclamations

- Notifications temps réel via Novu pour les changements de statut
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Reclamation

logger = logging.getLogger(__name__)

# Cache pour stocker l'ancien statut avant sauvegarde
_reclamation_previous_status = {}


@receiver(pre_save, sender=Reclamation)
def reclamation_pre_save(sender, instance, **kwargs):
    """
    Capture l'ancien statut avant modification pour détecter les changements.
    """
    if instance.pk:
        try:
            old_instance = Reclamation.objects.get(pk=instance.pk)
            _reclamation_previous_status[instance.pk] = old_instance.statut
            logger.info(f"[DEBUG-SIGNAL] Reclamation #{instance.pk} pre_save: old_statut={old_instance.statut}")
        except Reclamation.DoesNotExist:
            pass


@receiver(post_save, sender=Reclamation)
def reclamation_post_save(sender, instance, created, **kwargs):
    """
    Signal déclenché après sauvegarde d'une réclamation.
    Envoie les notifications appropriées selon l'action.
    """
    actor = getattr(instance, '_current_user', None)
    logger.info(f"[DEBUG-SIGNAL] Reclamation #{instance.id} post_save: created={created}, actor={actor}")
    try:
        from api.services.notifications import NotificationService

        if created:
            # Nouvelle réclamation créée
            logger.info(f"[NOTIF] Nouvelle réclamation créée: {instance.numero_reclamation}")
            NotificationService.notify_reclamation_creee(
                instance, 
                acteur=getattr(instance, '_current_user', None)
            )

        else:
            # Vérifier si le statut a changé
            old_statut = _reclamation_previous_status.pop(instance.pk, None)

            if old_statut and old_statut != instance.statut:
                logger.info(
                    f"[NOTIF] Réclamation {instance.numero_reclamation} "
                    f"statut: {old_statut} → {instance.statut}"
                )
                NotificationService.notify_reclamation_statut_change(
                    instance, 
                    old_statut, 
                    acteur=getattr(instance, '_current_user', None)
                )

    except Exception as e:
        logger.error(f"[NOTIF] Erreur notification réclamation {instance.numero_reclamation}: {e}")