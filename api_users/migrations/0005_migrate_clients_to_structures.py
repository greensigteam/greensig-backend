"""
Migration de données : Conversion des Clients en StructureClient

Cette migration:
1. Crée une StructureClient pour chaque Client existant
2. Lie chaque Client à sa nouvelle StructureClient
3. Met à jour les Sites pour pointer vers StructureClient
4. Met à jour les Taches pour pointer vers StructureClient
5. Met à jour les Reclamations pour pointer vers StructureClient
"""

from django.db import migrations


def migrate_clients_to_structures(apps, schema_editor):
    """
    Migre les données des Clients existants vers le nouveau modèle StructureClient.
    """
    Client = apps.get_model('api_users', 'Client')
    StructureClient = apps.get_model('api_users', 'StructureClient')
    Site = apps.get_model('api', 'Site')
    Tache = apps.get_model('api_planification', 'Tache')
    Reclamation = apps.get_model('api_reclamations', 'Reclamation')

    # Pour chaque client existant
    for client in Client.objects.all():
        # 1. Créer une StructureClient avec les données du client
        structure = StructureClient.objects.create(
            nom=client.nom_structure or f"Structure de {client.utilisateur.email}",
            adresse=client.adresse or "",
            telephone=client.telephone or "",
            contact_principal=client.contact_principal or "",
            email_facturation=client.email_facturation or "",
            logo=client.logo,
            actif=True,
        )

        # 2. Lier le client à sa structure
        client.structure = structure
        client.save()

        # 3. Migrer les sites de ce client vers la structure
        Site.objects.filter(client=client).update(structure_client=structure)

        # 4. Migrer les tâches de ce client vers la structure
        Tache.objects.filter(id_client=client).update(id_structure_client=structure)

        # 5. Migrer les réclamations de ce client vers la structure
        Reclamation.objects.filter(client=client).update(structure_client=structure)

    print(f"Migration terminée: {Client.objects.count()} clients convertis en structures")


def reverse_migration(apps, schema_editor):
    """
    Annule la migration (pour rollback).
    Note: Les StructureClients créées seront supprimées, mais les données legacy sont conservées.
    """
    Client = apps.get_model('api_users', 'Client')
    StructureClient = apps.get_model('api_users', 'StructureClient')

    # Supprimer le lien entre Client et StructureClient
    Client.objects.all().update(structure=None)

    # Réinitialiser les champs structure_client
    Site = apps.get_model('api', 'Site')
    Tache = apps.get_model('api_planification', 'Tache')
    Reclamation = apps.get_model('api_reclamations', 'Reclamation')

    Site.objects.all().update(structure_client=None)
    Tache.objects.all().update(id_structure_client=None)
    Reclamation.objects.all().update(structure_client=None)

    # Supprimer les StructureClients créées
    StructureClient.objects.all().delete()

    print("Rollback effectué: StructureClients supprimées")


class Migration(migrations.Migration):

    dependencies = [
        ('api_users', '0004_add_structure_client'),
        ('api', '0004_add_structure_client'),
        ('api_planification', '0003_add_structure_client'),
        ('api_reclamations', '0005_add_structure_client'),
    ]

    operations = [
        migrations.RunPython(
            migrate_clients_to_structures,
            reverse_code=reverse_migration,
        ),
    ]
