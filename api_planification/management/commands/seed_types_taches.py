from django.core.management.base import BaseCommand
from api_planification.models import TypeTache


class Command(BaseCommand):
    help = 'Peuple la table TypeTache avec les types de tâches standards et leur productivité théorique'

    def handle(self, *args, **options):
        self.stdout.write("Début du peuplement des types de tâches...")

        # Format: nom_tache, symbole, description, productivite_theorique, unite_productivite
        types_taches = [
            # ========== TÂCHES GÉNÉRALES ==========
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
            # ========== ARROSAGES SPÉCIFIQUES ==========
            {
                'nom_tache': 'Arrosage des arbres',
                'symbole': 'ARA',
                'description': 'Irrigation des arbres',
                'productivite_theorique': 40,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Arrosage des arbustes',
                'symbole': 'ARB',
                'description': 'Irrigation des arbustes',
                'productivite_theorique': 100,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrosage des palmiers',
                'symbole': 'ARP',
                'description': 'Irrigation des palmiers',
                'productivite_theorique': 40,
                'unite_productivite': 'palmiers'
            },
            {
                'nom_tache': 'Arrosage des graminées',
                'symbole': 'ARG',
                'description': 'Irrigation des graminées',
                'productivite_theorique': 40,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrosage des vivaces',
                'symbole': 'ARV',
                'description': 'Irrigation des vivaces',
                'productivite_theorique': 200,
                'unite_productivite': 'plantes'
            },
            {
                'nom_tache': 'Arrosage des cactus',
                'symbole': 'ARC',
                'description': 'Irrigation des cactus',
                'productivite_theorique': 200,
                'unite_productivite': 'plantes'
            },
            # ========== TAILLE ET ÉLAGAGE ==========
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
            # ========== TRAVAUX DU SOL ==========
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
                'nom_tache': 'Terreautage',
                'symbole': 'TER',
                'description': 'Apport de terreau pour enrichir le sol',
                'productivite_theorique': 37,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Apport de terre végétale',
                'symbole': 'ATV',
                'description': 'Apport de terre végétale pour améliorer la qualité du sol',
                'productivite_theorique': None,
                'unite_productivite': 'm3'
            },
            # ========== AÉRATIONS SPÉCIFIQUES ==========
            {
                'nom_tache': 'Aération des sols pour arbres',
                'symbole': 'AEA',
                'description': 'Perforation du sol autour des arbres pour améliorer la circulation de l\'air',
                'productivite_theorique': 60,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Aération des sols pour arbustes',
                'symbole': 'AEB',
                'description': 'Perforation du sol autour des arbustes pour améliorer la circulation de l\'air',
                'productivite_theorique': 100,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Aération des sols pour cactus',
                'symbole': 'AEC',
                'description': 'Perforation du sol autour des cactus pour améliorer la circulation de l\'air',
                'productivite_theorique': 40,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Aération des sols pour vivaces',
                'symbole': 'AEV',
                'description': 'Perforation du sol autour des vivaces pour améliorer la circulation de l\'air',
                'productivite_theorique': 80,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Aération des sols pour graminées',
                'symbole': 'AEG',
                'description': 'Perforation du sol autour des graminées pour améliorer la circulation de l\'air',
                'productivite_theorique': 200,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Aération des sols pour palmiers',
                'symbole': 'AEP',
                'description': 'Perforation du sol autour des palmiers pour améliorer la circulation de l\'air',
                'productivite_theorique': 80,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Aération des sols pour gazon',
                'symbole': 'AEZ',
                'description': 'Perforation du sol du gazon pour améliorer la circulation de l\'air',
                'productivite_theorique': None,
                'unite_productivite': 'm2'
            },
            # ========== REPLANTATION ==========
            {
                'nom_tache': 'Replantation',
                'symbole': 'REP',
                'description': 'Remplacement des végétaux morts ou malades',
                'productivite_theorique': 3,
                'unite_productivite': 'arbres'
            },
            # ========== ENTRETIEN GAZON ==========
            {
                'nom_tache': 'Topdressing gazon',
                'symbole': 'TDG',
                'description': 'Application de compost ou sable fin sur le gazon',
                'productivite_theorique': 40,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Compactage du gazon',
                'symbole': 'CPG',
                'description': 'Compactage et raffermissement de la surface du gazon',
                'productivite_theorique': 500,
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
                'nom_tache': 'Sursemis',
                'symbole': 'SUR',
                'description': 'Semis complémentaire pour régénérer le gazon',
                'productivite_theorique': 2100,
                'unite_productivite': 'm2'
            },
            # ========== DÉSHERBAGE ==========
            {
                'nom_tache': 'Désherbage manuel',
                'symbole': 'DEM',
                'description': 'Élimination manuelle des mauvaises herbes',
                'productivite_theorique': 15,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Désherbage chimique',
                'symbole': 'DEC',
                'description': 'Élimination des mauvaises herbes par produits chimiques',
                'productivite_theorique': 400,
                'unite_productivite': 'm2'
            },
            # ========== NETTOYAGE ET RAMASSAGE ==========
            {
                'nom_tache': 'Ramassage des déchets verts',
                'symbole': 'RAM',
                'description': 'Collecte et évacuation des déchets végétaux',
                'productivite_theorique': 56,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Traçage des bordures',
                'symbole': 'TBR',
                'description': 'Ajustement et alignement des bordures',
                'productivite_theorique': 18,
                'unite_productivite': 'ml'
            },
            # ========== ARRACHAGE DES VÉGÉTAUX MORTS ==========
            {
                'nom_tache': 'Arrachage des arbres morts',
                'symbole': 'AAM',
                'description': 'Extraction des arbres morts ou malades',
                'productivite_theorique': 1,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Arrachage des palmiers morts',
                'symbole': 'APM',
                'description': 'Extraction des palmiers morts ou malades',
                'productivite_theorique': 0.8,
                'unite_productivite': 'palmiers'
            },
            {
                'nom_tache': 'Arrachage des arbustes morts',
                'symbole': 'ABM',
                'description': 'Extraction des arbustes morts ou malades',
                'productivite_theorique': 5,
                'unite_productivite': 'arbustes'
            },
            {
                'nom_tache': 'Arrachage des graminées mortes',
                'symbole': 'AGM',
                'description': 'Extraction des graminées mortes',
                'productivite_theorique': 20,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrachage des cactus morts',
                'symbole': 'ACM',
                'description': 'Extraction des cactus morts',
                'productivite_theorique': 2,
                'unite_productivite': 'cactus'
            },
            {
                'nom_tache': 'Arrachage des vivaces mortes',
                'symbole': 'AVM',
                'description': 'Extraction des vivaces mortes',
                'productivite_theorique': 8,
                'unite_productivite': 'vivaces'
            },
            # ========== ENTRETIEN POTS INTÉRIEURS ==========
            {
                'nom_tache': 'Arrosage et entretien des pots intérieurs',
                'symbole': 'API',
                'description': 'Arrosage et entretien des plantes en pots à l\'intérieur',
                'productivite_theorique': None,
                'unite_productivite': 'pots'
            },
            # ========== HYDROLOGIE / IRRIGATION ==========
            {
                'nom_tache': 'Réparation des fuites',
                'symbole': 'RFU',
                'description': 'Réparation des fuites du système d\'irrigation',
                'productivite_theorique': None,
                'unite_productivite': 'unite'
            },
            {
                'nom_tache': 'Contrôle du système d\'irrigation',
                'symbole': 'CSI',
                'description': 'Vérification et contrôle du bon fonctionnement du système d\'irrigation',
                'productivite_theorique': None,
                'unite_productivite': 'unite'
            },
            # ========== ENTRETIEN OUTILLAGE ==========
            {
                'nom_tache': 'Nettoyage et désinfection de l\'outillage',
                'symbole': 'NDO',
                'description': 'Nettoyage et désinfection des outils de travail',
                'productivite_theorique': None,
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
