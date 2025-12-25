"""
Signals pour le module Planification

Auto-remplissage du champ id_client basé sur les objets liés à la tâche.
"""

from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import Tache


@receiver(m2m_changed, sender=Tache.objets.through)
def auto_assign_client_from_objects(sender, instance, action, **kwargs):
    """
    Signal qui remplit automatiquement id_client quand des objets sont ajoutés à une tâche.

    Fonctionnement:
    - Quand des objets sont ajoutés à une tâche (action='post_add')
    - Récupère le site du premier objet
    - Récupère le client du site
    - Assigne ce client à la tâche

    Cela permet de maintenir la cohérence entre:
    - Relation directe: Tâche.id_client → Client
    - Relation indirecte: Tâche → Objets → Site → Client
    """

    # On agit seulement APRÈS l'ajout d'objets
    if action != 'post_add':
        return

    # Si la tâche a déjà un client assigné manuellement, on respecte ce choix
    if instance.id_client is not None:
        return

    # Récupérer le premier objet avec site et client
    objets = instance.objets.select_related('site__client').all()

    for obj in objets:
        if obj.site and obj.site.client:
            # Assigner le client du site à la tâche
            instance.id_client = obj.site.client
            instance.save(update_fields=['id_client'])

            print(f"✅ [AUTO-ASSIGN] Tâche #{instance.id} → Client '{obj.site.client.nom_structure}'")
            break

    # Si aucun client trouvé, logger un avertissement
    else:
        if objets.exists():
            print(f"⚠️  [AUTO-ASSIGN] Tâche #{instance.id}: objets sans site ou site sans client")


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
            print(
                f"⚠️  [VALIDATION] Tâche #{instance.id}: "
                f"id_client={tache_client_id} mais objets appartiennent à {clients_found}"
            )

        if len(clients_found) > 1:
            print(
                f"⚠️  [VALIDATION] Tâche #{instance.id}: "
                f"objets appartiennent à plusieurs clients {clients_found}"
            )
