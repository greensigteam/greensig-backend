from django.db import migrations


def seed_types_taches(apps, schema_editor):
    """Peuple la table TypeTache avec les types de tâches standards."""
    TypeTache = apps.get_model('api_planification', 'TypeTache')

    types_taches = [
        {'nom_tache': 'Nettoyage', 'symbole': 'NET', 'description': 'Nettoyage général des espaces verts'},
        {'nom_tache': 'Binage', 'symbole': 'BIN', 'description': 'Travail du sol pour aérer et désherber'},
        {'nom_tache': 'Confection cuvette', 'symbole': 'CUV', 'description': 'Création de cuvettes autour des végétaux pour retenir l\'eau'},
        {'nom_tache': 'Traitement', 'symbole': 'TRT', 'description': 'Application de produits phytosanitaires'},
        {'nom_tache': 'Arrosage', 'symbole': 'ARR', 'description': 'Irrigation des végétaux'},
        {'nom_tache': 'Élagage', 'symbole': 'ELA', 'description': 'Taille des branches d\'arbres'},
        {'nom_tache': 'Tuteurage', 'symbole': 'TUT', 'description': 'Installation de tuteurs pour soutenir les jeunes plants'},
        {'nom_tache': 'Sablage', 'symbole': 'SAB', 'description': 'Épandage de sable sur les surfaces'},
        {'nom_tache': 'Fertilisation', 'symbole': 'FER', 'description': 'Apport d\'engrais aux végétaux'},
        {'nom_tache': 'Paillage', 'symbole': 'PAI', 'description': 'Mise en place de paillis pour protéger le sol'},
        {'nom_tache': 'Nivellement du sol', 'symbole': 'NIV', 'description': 'Égalisation de la surface du sol'},
        {'nom_tache': 'Aération des sols', 'symbole': 'AER', 'description': 'Perforation du sol pour améliorer la circulation de l\'air'},
        {'nom_tache': 'Replantation', 'symbole': 'REP', 'description': 'Remplacement des végétaux morts ou malades'},
        {'nom_tache': 'Taille de formation', 'symbole': 'TFO', 'description': 'Taille pour donner une forme aux jeunes végétaux'},
        {'nom_tache': 'Taille d\'entretien', 'symbole': 'TEN', 'description': 'Taille régulière pour maintenir la forme et la santé'},
        {'nom_tache': 'Terreautage', 'symbole': 'TER', 'description': 'Apport de terreau pour enrichir le sol'},
        {'nom_tache': 'Scarification', 'symbole': 'SCA', 'description': 'Élimination du feutre et de la mousse des gazons'},
        {'nom_tache': 'Tonte', 'symbole': 'TON', 'description': 'Coupe régulière du gazon'},
        {'nom_tache': 'Ramassage des déchets verts', 'symbole': 'RAM', 'description': 'Collecte et évacuation des déchets végétaux'},
        {'nom_tache': 'Désherbage', 'symbole': 'DES', 'description': 'Élimination des mauvaises herbes'},
        {'nom_tache': 'Nivellement des bordures', 'symbole': 'NBR', 'description': 'Ajustement et alignement des bordures'},
        {'nom_tache': 'Arrachage des plantes mortes', 'symbole': 'APM', 'description': 'Extraction des végétaux morts'},
        {'nom_tache': 'Réparation des fuites', 'symbole': 'RFU', 'description': 'Réparation des fuites du système d\'irrigation'},
    ]

    for data in types_taches:
        TypeTache.objects.get_or_create(
            nom_tache=data['nom_tache'],
            defaults=data
        )


def reverse_seed(apps, schema_editor):
    """Supprime les types de tâches créés par cette migration."""
    TypeTache = apps.get_model('api_planification', 'TypeTache')
    noms = [
        'Nettoyage', 'Binage', 'Confection cuvette', 'Traitement', 'Arrosage',
        'Élagage', 'Tuteurage', 'Sablage', 'Fertilisation', 'Paillage',
        'Nivellement du sol', 'Aération des sols', 'Replantation',
        'Taille de formation', 'Taille d\'entretien', 'Terreautage',
        'Scarification', 'Tonte', 'Ramassage des déchets verts', 'Désherbage',
        'Nivellement des bordures', 'Arrachage des plantes mortes',
        'Réparation des fuites',
    ]
    TypeTache.objects.filter(nom_tache__in=noms).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('api_planification', '0008_tache_commentaire_validation_tache_date_validation_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_types_taches, reverse_seed),
    ]
