"""
Taches Celery pour le module Reclamations.

- auto_close_pending_reclamations: Toutes les heures
  1. Auto-cloture apres 48h sans reponse du client
  2. Rappel a 24h si pas encore envoye
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

logger = logging.getLogger(__name__)


@shared_task(name='api_reclamations.tasks.auto_close_pending_reclamations')
def auto_close_pending_reclamations():
    """
    Tache periodique (toutes les heures):
    1. Auto-cloture les reclamations EN_ATTENTE_VALIDATION_CLOTURE depuis >= 48h
    2. Envoie un rappel a 24h pour celles pas encore rappelees

    Idempotente: les auto-cloturees ne sont plus EN_ATTENTE_VALIDATION_CLOTURE,
    les rappelees ont rappel_cloture_envoye=True.
    """
    from api_reclamations.models import Reclamation, HistoriqueReclamation
    from api.services.notifications import NotificationService, NotificationTypes

    now = timezone.now()
    seuil_48h = now - timedelta(hours=48)
    seuil_24h = now - timedelta(hours=24)

    auto_closed_count = 0
    reminder_count = 0

    # ===================================================================
    # PASSE 1: Auto-cloture (>= 48h) — traite en premier pour eviter
    # d'envoyer un rappel inutile a une reclamation qu'on va cloturer
    # ===================================================================
    reclamations_to_close = Reclamation.objects.filter(
        statut='EN_ATTENTE_VALIDATION_CLOTURE',
        date_proposition_cloture__lte=seuil_48h,
    )

    for reclamation in reclamations_to_close:
        try:
            with transaction.atomic():
                old_statut = reclamation.statut
                reclamation.statut = 'CLOTUREE'
                reclamation._current_user = None  # Action systeme
                reclamation.save()

                # Historique
                HistoriqueReclamation.objects.create(
                    reclamation=reclamation,
                    statut_precedent=old_statut,
                    statut_nouveau='CLOTUREE',
                    auteur=None,
                    commentaire="Cloture automatique apres 48h sans reponse du client"
                )

                # Notification au createur
                if reclamation.createur:
                    NotificationService.send(
                        type_notification=NotificationTypes.RECLAMATION_AUTO_CLOTURE,
                        titre=f"Reclamation {reclamation.numero_reclamation} auto-cloturee",
                        message="La reclamation a ete automatiquement cloturee apres 48h sans reponse de votre part.",
                        recipients=[reclamation.createur],
                        data={
                            'reclamation_id': reclamation.id,
                            'numero': reclamation.numero_reclamation,
                            'site': reclamation.site.nom_site if reclamation.site else '',
                        },
                        priorite='high',
                    )

                auto_closed_count += 1
                logger.info(
                    f"[AUTO-CLOTURE] Reclamation {reclamation.numero_reclamation} "
                    f"auto-cloturee (proposition: {reclamation.date_proposition_cloture})"
                )

        except Exception as e:
            logger.error(
                f"[AUTO-CLOTURE] Erreur pour reclamation {reclamation.numero_reclamation}: {e}"
            )

    # ===================================================================
    # PASSE 2: Rappel (>= 24h et < 48h, pas encore rappele)
    # ===================================================================
    reclamations_to_remind = Reclamation.objects.filter(
        statut='EN_ATTENTE_VALIDATION_CLOTURE',
        date_proposition_cloture__lte=seuil_24h,
        date_proposition_cloture__gt=seuil_48h,
        rappel_cloture_envoye=False,
    )

    for reclamation in reclamations_to_remind:
        try:
            # Marquer le rappel comme envoye (update_fields pour eviter les signals)
            reclamation.rappel_cloture_envoye = True
            reclamation.save(update_fields=['rappel_cloture_envoye'])

            # Notification au createur
            if reclamation.createur:
                NotificationService.send(
                    type_notification=NotificationTypes.RECLAMATION_RAPPEL_CLOTURE,
                    titre=f"Rappel: validez la cloture de {reclamation.numero_reclamation}",
                    message="Une proposition de cloture attend votre validation. Sans reponse sous 24h, la reclamation sera automatiquement cloturee.",
                    recipients=[reclamation.createur],
                    data={
                        'reclamation_id': reclamation.id,
                        'numero': reclamation.numero_reclamation,
                        'site': reclamation.site.nom_site if reclamation.site else '',
                    },
                    priorite='high',
                )

            reminder_count += 1
            logger.info(
                f"[RAPPEL-CLOTURE] Rappel envoye pour reclamation {reclamation.numero_reclamation}"
            )

        except Exception as e:
            logger.error(
                f"[RAPPEL-CLOTURE] Erreur pour reclamation {reclamation.numero_reclamation}: {e}"
            )

    # ===================================================================
    # Invalidation du cache si des reclamations ont ete auto-cloturees
    # ===================================================================
    if auto_closed_count > 0:
        try:
            from greensig_web.cache_utils import invalidate_on_reclamation_mutation
            invalidate_on_reclamation_mutation()
        except Exception as e:
            logger.warning(f"[AUTO-CLOTURE] Erreur invalidation cache: {e}")

    logger.info(
        f"[AUTO-CLOTURE] Termine: {auto_closed_count} auto-cloturee(s), "
        f"{reminder_count} rappel(s) envoye(s)"
    )

    return {
        'auto_closed': auto_closed_count,
        'reminders_sent': reminder_count,
    }
