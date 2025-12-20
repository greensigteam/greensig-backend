from django.db import migrations


def seed_types_reclamations(apps, schema_editor):
    """Peuple la table TypeReclamation avec les types standards."""
    TypeReclamation = apps.get_model('api_reclamations', 'TypeReclamation')

    types_reclamations = [
        # URGENCE
        {'nom_reclamation': 'Fuite d\'eau', 'code_reclamation': 'URG-FUITE', 'categorie': 'URGENCE', 'symbole': '💧'},
        {'nom_reclamation': 'Équipement en panne', 'code_reclamation': 'URG-PANNE', 'categorie': 'URGENCE', 'symbole': '⚠️'},

        # QUALITE
        {'nom_reclamation': 'Végétation arrachée', 'code_reclamation': 'QLT-ARRACHEE', 'categorie': 'QUALITE', 'symbole': '🌿'},
        {'nom_reclamation': 'Zone dégradée', 'code_reclamation': 'QLT-DEGRADEE', 'categorie': 'QUALITE', 'symbole': '📍'},
        {'nom_reclamation': 'Manque entretien', 'code_reclamation': 'QLT-ENTRETIEN', 'categorie': 'QUALITE', 'symbole': '🔧'},
        {'nom_reclamation': 'Maladie', 'code_reclamation': 'QLT-MALADIE', 'categorie': 'QUALITE', 'symbole': '🦠'},
        {'nom_reclamation': 'Ravageur', 'code_reclamation': 'QLT-RAVAGEUR', 'categorie': 'QUALITE', 'symbole': '🐛'},
        {'nom_reclamation': 'Plantes mortes', 'code_reclamation': 'QLT-MORTES', 'categorie': 'QUALITE', 'symbole': '🥀'},
        {'nom_reclamation': 'Sol compacté', 'code_reclamation': 'QLT-SOL', 'categorie': 'QUALITE', 'symbole': '🪨'},
        {'nom_reclamation': 'Accumulation de déchets verts', 'code_reclamation': 'QLT-DECHETS', 'categorie': 'QUALITE', 'symbole': '🍂'},

        # PLANNING
        {'nom_reclamation': 'Zone à prioriser', 'code_reclamation': 'PLN-PRIORITE', 'categorie': 'PLANNING', 'symbole': '⭐'},
        {'nom_reclamation': 'Évènement planifié', 'code_reclamation': 'PLN-EVENT', 'categorie': 'PLANNING', 'symbole': '📅'},
        {'nom_reclamation': 'Retard des équipes', 'code_reclamation': 'PLN-RETARD', 'categorie': 'PLANNING', 'symbole': '⏰'},
        {'nom_reclamation': 'Planning non respecté', 'code_reclamation': 'PLN-NONRESP', 'categorie': 'PLANNING', 'symbole': '📋'},

        # RESSOURCES
        {'nom_reclamation': 'Manque matériel', 'code_reclamation': 'RES-MATERIEL', 'categorie': 'RESSOURCES', 'symbole': '🛠️'},
        {'nom_reclamation': 'Manque effectif', 'code_reclamation': 'RES-EFFECTIF', 'categorie': 'RESSOURCES', 'symbole': '👷'},
    ]

    for data in types_reclamations:
        TypeReclamation.objects.get_or_create(
            code_reclamation=data['code_reclamation'],
            defaults=data
        )


def reverse_seed(apps, schema_editor):
    """Supprime les types de réclamations créés par cette migration."""
    TypeReclamation = apps.get_model('api_reclamations', 'TypeReclamation')
    codes = [
        'URG-FUITE', 'URG-PANNE',
        'QLT-ARRACHEE', 'QLT-DEGRADEE', 'QLT-ENTRETIEN', 'QLT-MALADIE',
        'QLT-RAVAGEUR', 'QLT-MORTES', 'QLT-SOL', 'QLT-DECHETS',
        'PLN-PRIORITE', 'PLN-EVENT', 'PLN-RETARD', 'PLN-NONRESP',
        'RES-MATERIEL', 'RES-EFFECTIF',
    ]
    TypeReclamation.objects.filter(code_reclamation__in=codes).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api_reclamations', '0006_add_createur_field'),
    ]

    operations = [
        migrations.RunPython(seed_types_reclamations, reverse_seed),
    ]
