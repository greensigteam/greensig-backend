from django.core.management.base import BaseCommand
from api_planification.models import TypeTache


class Command(BaseCommand):
    help = 'Peuple la table TypeTache avec les types de tâches standards et leur productivité théorique'

    def handle(self, *args, **options):
        self.stdout.write("Début du peuplement des types de tâches...")

        # Format: nom_tache, symbole, description, productivite_theorique, unite_productivite
        types_taches = [
            {
                'nom_tache': 'Nettoyage',
                'symbole': 'NET',
                'description': 'Nettoyage général des espaces verts',
                'productivite_theorique': 90,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Binage',
                'symbole': 'BIN',
                'description': 'Travail du sol pour aérer et désherber',
                'productivite_theorique': 60,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Confection cuvette',
                'symbole': 'CUV',
                'description': 'Création de cuvettes autour des végétaux pour retenir l\'eau',
                'productivite_theorique': 8,
                'unite_productivite': 'cuvettes'
            },
            {
                'nom_tache': 'Traitement',
                'symbole': 'TRT',
                'description': 'Application de produits phytosanitaires',
                'productivite_theorique': 190,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrosage',
                'symbole': 'ARR',
                'description': 'Irrigation des végétaux',
                'productivite_theorique': 250,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Élagage',
                'symbole': 'ELA',
                'description': 'Taille des branches d\'arbres',
                'productivite_theorique': 1,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Tuteurage',
                'symbole': 'TUT',
                'description': 'Installation de tuteurs pour soutenir les jeunes plants',
                'productivite_theorique': 7,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Sablage',
                'symbole': 'SAB',
                'description': 'Épandage de sable sur les surfaces',
                'productivite_theorique': 37,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Fertilisation',
                'symbole': 'FER',
                'description': 'Apport d\'engrais aux végétaux',
                'productivite_theorique': 180,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Paillage',
                'symbole': 'PAI',
                'description': 'Mise en place de paillis pour protéger le sol',
                'productivite_theorique': 37,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Nivellement du sol',
                'symbole': 'NIV',
                'description': 'Égalisation de la surface du sol',
                'productivite_theorique': 60,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Aération des sols',
                'symbole': 'AER',
                'description': 'Perforation du sol pour améliorer la circulation de l\'air',
                'productivite_theorique': 90,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Replantation',
                'symbole': 'REP',
                'description': 'Remplacement des végétaux morts ou malades',
                'productivite_theorique': 3,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Taille de formation',
                'symbole': 'TFO',
                'description': 'Taille pour donner une forme aux jeunes végétaux',
                'productivite_theorique': 2,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Taille d\'entretien',
                'symbole': 'TEN',
                'description': 'Taille régulière pour maintenir la forme et la santé',
                'productivite_theorique': 3,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Terreautage',
                'symbole': 'TER',
                'description': 'Apport de terreau pour enrichir le sol',
                'productivite_theorique': 37,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Scarification',
                'symbole': 'SCA',
                'description': 'Élimination du feutre et de la mousse des gazons',
                'productivite_theorique': 75,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Tonte',
                'symbole': 'TON',
                'description': 'Coupe régulière du gazon',
                'productivite_theorique': 1000,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Ramassage des déchets verts',
                'symbole': 'RAM',
                'description': 'Collecte et évacuation des déchets végétaux',
                'productivite_theorique': 56,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Désherbage',
                'symbole': 'DES',
                'description': 'Élimination des mauvaises herbes',
                'productivite_theorique': 15,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Nivellement des bordures',
                'symbole': 'NBR',
                'description': 'Ajustement et alignement des bordures',
                'productivite_theorique': 18,
                'unite_productivite': 'ml'
            },
            {
                'nom_tache': 'Arrachage des plantes mortes',
                'symbole': 'APM',
                'description': 'Extraction des végétaux morts',
                'productivite_theorique': 18,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Réparation des fuites',
                'symbole': 'RFU',
                'description': 'Réparation des fuites du système d\'irrigation',
                'productivite_theorique': None,  # Pas de productivité standard pour cette tâche
                'unite_productivite': 'unite'
            },
        ]

        created_count = 0
        updated_count = 0

        for data in types_taches:
            obj, created = TypeTache.objects.update_or_create(
                nom_tache=data['nom_tache'],
                defaults=data
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Type créé: {obj.nom_tache}'))
            else:
                updated_count += 1
                self.stdout.write(f'  Type mis à jour: {obj.nom_tache}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Peuplement terminé: {created_count} types créés, {updated_count} mis à jour'
        ))
