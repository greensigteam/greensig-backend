"""
Signals pour le module Planification

- Auto-remplissage du champ id_client basé sur les objets liés à la tâche
- Notifications temps réel via Novu
"""

import logging
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from .models import Tache

logger = logging.getLogger(__name__)

# Debug: api_planification.signals LOADED


def update_last_intervention_date(tache):
    """
    Met à jour le champ last_intervention_date sur tous les objets liés à une tâche terminée.
    Utilise la date de fin réelle de la tâche ou la date courante.
    """
    from django.utils import timezone
    from api.models import (
        Arbre, Palmier, Gazon, Arbuste, Vivace, Cactus, Graminee,
        Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
    )

    # Date à utiliser: date_fin_reelle ou date du jour
    intervention_date = tache.date_fin_reelle.date() if tache.date_fin_reelle else timezone.now().date()

    # Récupérer tous les objets liés à cette tâche
    objets = tache.objets.all()

    if not objets.exists():
        logger.debug(f"[LAST_INTERVENTION] Tache #{tache.id}: aucun objet lié")
        return

    updated_count = 0
    for objet in objets:
        # Obtenir l'instance réelle (enfant polymorphique)
        real_obj = objet.get_type_reel()
        if real_obj and hasattr(real_obj, 'last_intervention_date'):
            real_obj.last_intervention_date = intervention_date
            real_obj.save(update_fields=['last_intervention_date'])
            updated_count += 1

    logger.info(f"[LAST_INTERVENTION] Tache #{tache.id} TERMINEE: {updated_count} objets mis à jour avec date {intervention_date}")


@receiver(m2m_changed, sender=Tache.objets.through)
def auto_assign_client_from_objects(sender, instance, action, **kwargs):
    """
    Signal qui remplit automatiquement id_client et id_structure_client quand des objets sont ajoutés à une tâche.

    Fonctionnement:
    - Quand des objets sont ajoutés à une tâche (action='post_add')
    - Récupère le site du premier objet
    - Récupère le client et la structure_client du site
    - Assigne ces valeurs à la tâche

    Cela permet de maintenir la cohérence entre:
    - Relation directe: Tâche.id_client → Client
    - Relation directe: Tâche.id_structure_client → StructureClient
    - Relation indirecte: Tâche → Objets → Site → Client/StructureClient
    """

    # On agit seulement APRÈS l'ajout d'objets
    if action != 'post_add':
        return

    # Récupérer le premier objet avec site, client et structure_client
    objets = instance.objets.select_related('site__client', 'site__structure_client').all()

    update_fields = []

    for obj in objets:
        if obj.site:
            # Assigner le client du site à la tâche (si pas déjà défini)
            if instance.id_client is None and obj.site.client:
                instance.id_client = obj.site.client
                update_fields.append('id_client')
                logger.info(f"[AUTO-ASSIGN] Tache #{instance.id} -> Client '{obj.site.client.nom_structure}'")

            # Assigner la structure client du site à la tâche (si pas déjà défini)
            if instance.id_structure_client is None and obj.site.structure_client:
                instance.id_structure_client = obj.site.structure_client
                update_fields.append('id_structure_client')
                logger.info(f"[AUTO-ASSIGN] Tache #{instance.id} -> StructureClient '{obj.site.structure_client.nom}'")

            # Si on a trouvé au moins une valeur, on sort de la boucle
            if update_fields:
                break

    # Sauvegarder si des champs ont été mis à jour
    if update_fields:
        instance.save(update_fields=update_fields)

    # Si aucun client/structure trouvé, logger un avertissement
    if not update_fields and objets.exists():
        logger.warning(f"[AUTO-ASSIGN] Tache #{instance.id}: objets sans site ou site sans client/structure")


@receiver(m2m_changed, sender=Tache.objets.through)
def validate_client_consistency(sender, instance, action, **kwargs):
    """
    Valide que tous les objets d'une tâche appartiennent au même client.

    Vérifie la cohérence entre id_client et les clients des sites des objets.
    """

    # On valide APRÈS l'ajout d'objets
    if action != 'post_add':
        return

    # Si pas de client assigné, pas de validation
    if instance.id_client is None:
        return

    # Récupérer tous les clients via les sites des objets
    objets = instance.objets.select_related('site__client').all()
    clients_found = set()

    for obj in objets:
        if obj.site and obj.site.client:
            clients_found.add(obj.site.client.utilisateur_id)

    # Vérifier la cohérence
    if clients_found:
        tache_client_id = instance.id_client.utilisateur_id

        if tache_client_id not in clients_found:
            logger.warning(
                f"[VALIDATION] Tache #{instance.id}: "
                f"id_client={tache_client_id} mais objets appartiennent a {clients_found}"
            )

        if len(clients_found) > 1:
            logger.warning(
                f"[VALIDATION] Tache #{instance.id}: "
                f"objets appartiennent a plusieurs clients {clients_found}"
            )


# =============================================================================
# NOTIFICATIONS TÂCHES
# =============================================================================

# Cache pour stocker l'ancien statut avant sauvegarde
_tache_previous_status = {}

# Note: On utilise désormais le champ 'notifiee' du modèle Tache pour la persistance 
# au lieu des caches en mémoire qui ne sont pas multi-process safe.


@receiver(pre_save, sender=Tache)
def tache_pre_save(sender, instance, **kwargs):
    """
    Capture l'ancien statut avant modification pour détecter les changements.
    """
    if instance.pk:
        try:
            old_instance = Tache.objects.get(pk=instance.pk)
            _tache_previous_status[instance.pk] = old_instance.statut
        except Tache.DoesNotExist:
            pass


@receiver(post_save, sender=Tache)
def tache_post_save(sender, instance, created, **kwargs):
    """
    Signal declenche apres sauvegarde d'une tache.
    Gere les changements de statut (la notification de creation est dans m2m_changed).
    """
    logger.debug(f"[DEBUG] tache_post_save TRIGGERED for Tache #{instance.id} created={created}")
    try:
        from api.services.notifications import NotificationService

        if created:
            # Pour une nouvelle tâche, on attend l'ajout d'objets (m2m_changed)
            # pour envoyer la notification de création avec les infos du site.
            logger.debug(f"[NOTIF] Tache #{instance.id} creee, en attente d'objets...")
            pass
        else:
            # Verifier si le statut a change
            old_statut = _tache_previous_status.pop(instance.pk, None)

            if old_statut and old_statut != instance.statut:
                logger.info(f"[NOTIF] Tache #{instance.id} statut: {old_statut} -> {instance.statut}")

                if instance.statut == 'TERMINEE':
                    NotificationService.notify_tache_terminee(
                        instance,
                        createur=getattr(instance, '_current_user', None)
                    )

                    # Mettre à jour last_intervention_date sur tous les objets liés
                    update_last_intervention_date(instance)

    except Exception as e:
        logger.error(f"[NOTIF] Erreur notification tache #{instance.id}: {e}")


@receiver(m2m_changed, sender=Tache.objets.through)
def notify_tache_on_objects_added(sender, instance, action, **kwargs):
    """
    Envoie la notification de creation APRES que les objets sont lies a la tache.
    C'est ici qu'on peut recuperer le site via tache.objets.
    """
    if action != 'post_add':
        return

    # Si la tâche est déjà notifiée ou n'a pas encore d'objets (sécurité)
    if instance.notifiee:
        return

    # Vérifier s'il y a des objets (indispensable pour le site)
    if not instance.objets.exists():
        return

    try:
        from api.services.notifications import NotificationService

        logger.info(f"[NOTIF] Objets ajoutes a tache #{instance.id}, envoi notification...")

        # Marquer comme notifiee persistante
        instance.notifiee = True
        instance.save(update_fields=['notifiee'])

        NotificationService.notify_tache_creee(
            instance, 
            createur=getattr(instance, '_current_user', None)
        )


    except Exception as e:
        logger.error(f"[NOTIF] Erreur notification tache #{instance.id} apres ajout objets: {e}")
