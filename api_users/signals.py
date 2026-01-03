"""
Signals pour le module Utilisateurs

- Notifications pour les absences (via Django Channels)
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Absence

logger = logging.getLogger(__name__)


# =============================================================================
# NOTIFICATIONS ABSENCES
# =============================================================================

# Cache pour stocker l'ancien statut avant sauvegarde
_absence_previous_status = {}


@receiver(pre_save, sender=Absence)
def absence_pre_save(sender, instance, **kwargs):
    """
    Capture l'ancien statut avant modification pour detecter les changements.
    """
    if instance.pk:
        try:
            old_instance = Absence.objects.get(pk=instance.pk)
            _absence_previous_status[instance.pk] = old_instance.statut
        except Absence.DoesNotExist:
            pass


@receiver(post_save, sender=Absence)
def absence_post_save(sender, instance, created, **kwargs):
    """
    Signal declenche apres sauvegarde d'une absence.
    Envoie les notifications appropriees selon l'action.
    """
    try:
        from api.services.notifications import NotificationService

        if created:
            # Nouvelle demande d'absence
            logger.info(f"[NOTIF] Nouvelle absence creee: {instance.id}")
            NotificationService.notify_absence_demandee(
                instance, 
                acteur=getattr(instance, '_current_user', None)
            )

        else:
            # Verifier si le statut a change
            old_statut = _absence_previous_status.pop(instance.pk, None)

            if old_statut and old_statut != instance.statut:
                logger.info(f"[NOTIF] Absence #{instance.id} statut: {old_statut} -> {instance.statut}")

                if instance.statut == 'VALIDEE':
                    NotificationService.notify_absence_validee(
                        instance, 
                        acteur=getattr(instance, '_current_user', None)
                    )
                elif instance.statut == 'REFUSEE':
                    motif = getattr(instance, 'motif_refus', '') or ''
                    NotificationService.notify_absence_refusee(
                        instance, 
                        motif, 
                        acteur=getattr(instance, '_current_user', None)
                    )

    except Exception as e:
        logger.error(f"[NOTIF] Erreur notification absence #{instance.id}: {e}")