from django.core.management.base import BaseCommand
from api_planification.models import TypeTache


class Command(BaseCommand):
    help = 'Peuple la table TypeTache avec les types de tâches standards et leur productivité théorique'

    def handle(self, *args, **options):
        self.stdout.write("Début du peuplement des types de tâches...")

        # Format: nom_tache, symbole, description, productivite_theorique, unite_productivite
        # Ratios basés sur le tableau de productivité théorique fourni
        types_taches = [
            # ========== NETTOYAGE ==========
            {
                'nom_tache': 'Nettoyage',
                'symbole': 'NET',
                'description': 'Nettoyage général des espaces verts (surfaces)',
                'productivite_theorique': 90,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Nettoyage des arbres',
                'symbole': 'NETA',
                'description': 'Nettoyage autour des arbres',
                'productivite_theorique': 6,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Nettoyage des palmiers',
                'symbole': 'NETP',
                'description': 'Nettoyage autour des palmiers',
                'productivite_theorique': 5,
                'unite_productivite': 'palmiers'
            },
            # ========== BINAGE ==========
            {
                'nom_tache': 'Binage',
                'symbole': 'BIN',
                'description': 'Travail du sol pour aérer et désherber (général)',
                'productivite_theorique': 60,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Binage des arbustes',
                'symbole': 'BINB',
                'description': 'Binage autour des arbustes',
                'productivite_theorique': 60,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Binage des vivaces',
                'symbole': 'BINV',
                'description': 'Binage autour des vivaces',
                'productivite_theorique': 50,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Binage des cactus',
                'symbole': 'BINC',
                'description': 'Binage autour des cactus',
                'productivite_theorique': 30,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Binage des graminées',
                'symbole': 'BING',
                'description': 'Binage autour des graminées',
                'productivite_theorique': 60,
                'unite_productivite': 'm2'
            },
            # ========== CONFECTION CUVETTE ==========
            {
                'nom_tache': 'Confection cuvette',
                'symbole': 'CUV',
                'description': 'Création de cuvettes autour des végétaux pour retenir l\'eau',
                'productivite_theorique': 8,
                'unite_productivite': 'cuvettes'
            },
            # ========== TRAITEMENT ==========
            {
                'nom_tache': 'Traitement',
                'symbole': 'TRT',
                'description': 'Application de produits phytosanitaires (surfaces)',
                'productivite_theorique': 190,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Traitement des arbres',
                'symbole': 'TRTA',
                'description': 'Traitement phytosanitaire des arbres',
                'productivite_theorique': 20,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Traitement des palmiers',
                'symbole': 'TRTP',
                'description': 'Traitement phytosanitaire des palmiers',
                'productivite_theorique': 20,
                'unite_productivite': 'palmiers'
            },
            # ========== ARROSAGE ==========
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
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrosage des cactus',
                'symbole': 'ARC',
                'description': 'Irrigation des cactus',
                'productivite_theorique': 200,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrosage du gazon',
                'symbole': 'ARZ',
                'description': 'Irrigation du gazon',
                'productivite_theorique': 80,
                'unite_productivite': 'm2'
            },
            # ========== ÉLAGAGE ==========
            {
                'nom_tache': 'Élagage',
                'symbole': 'ELA',
                'description': 'Taille des branches d\'arbres',
                'productivite_theorique': 1,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Élagage des palmiers',
                'symbole': 'ELAP',
                'description': 'Taille des palmes sèches et entretien des palmiers',
                'productivite_theorique': 2,
                'unite_productivite': 'palmiers'
            },
            # ========== TUTEURAGE ==========
            {
                'nom_tache': 'Tuteurage des arbres',
                'symbole': 'TUTA',
                'description': 'Installation de tuteurs pour soutenir les jeunes arbres',
                'productivite_theorique': 7,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Tuteurage des palmiers',
                'symbole': 'TUTP',
                'description': 'Installation de tuteurs pour soutenir les jeunes palmiers',
                'productivite_theorique': 7,
                'unite_productivite': 'palmiers'
            },
            {
                'nom_tache': 'Tuteurage des arbustes',
                'symbole': 'TUTB',
                'description': 'Installation de tuteurs pour soutenir les arbustes',
                'productivite_theorique': 7,
                'unite_productivite': 'm2'
            },
            # ========== SABLAGE ==========
            # Note: Le sablage s'applique uniquement au gazon
            {
                'nom_tache': 'Sablage',
                'symbole': 'SAB',
                'description': 'Épandage de sable sur le gazon pour améliorer le drainage',
                'productivite_theorique': 37,
                'unite_productivite': 'm2'
            },
            # ========== FERTILISATION ==========
            {
                'nom_tache': 'Fertilisation',
                'symbole': 'FER',
                'description': 'Apport d\'engrais aux végétaux (surfaces)',
                'productivite_theorique': 180,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Fertilisation chimique',
                'symbole': 'FERC',
                'description': 'Apport d\'engrais chimiques aux végétaux',
                'productivite_theorique': 200,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Fertilisation organique',
                'symbole': 'FERO',
                'description': 'Apport d\'engrais organiques (compost, fumier) aux végétaux',
                'productivite_theorique': 150,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Fertilisation des arbres',
                'symbole': 'FERA',
                'description': 'Fertilisation des arbres',
                'productivite_theorique': 20,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Fertilisation des palmiers',
                'symbole': 'FERP',
                'description': 'Fertilisation des palmiers',
                'productivite_theorique': 20,
                'unite_productivite': 'palmiers'
            },
            # ========== PAILLAGE ==========
            {
                'nom_tache': 'Paillage',
                'symbole': 'PAI',
                'description': 'Mise en place de paillis pour protéger le sol (surfaces)',
                'productivite_theorique': 37,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Paillage des arbres',
                'symbole': 'PAIA',
                'description': 'Paillage autour des arbres',
                'productivite_theorique': 15,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Paillage des palmiers',
                'symbole': 'PAIP',
                'description': 'Paillage autour des palmiers',
                'productivite_theorique': 10,
                'unite_productivite': 'palmiers'
            },
            # ========== NIVELLEMENT ==========
            {
                'nom_tache': 'Nivellement du sol',
                'symbole': 'NIV',
                'description': 'Égalisation de la surface du sol',
                'productivite_theorique': 60,
                'unite_productivite': 'm2'
            },
            # ========== AÉRATION DES SOLS ==========
            {
                'nom_tache': 'Aération des sols pour gazon',
                'symbole': 'AEZ',
                'description': 'Perforation du sol du gazon pour améliorer la circulation de l\'air',
                'productivite_theorique': 90,
                'unite_productivite': 'm2'
            },
            # ========== REPLANTATION ==========
            {
                'nom_tache': 'Replantation des arbres',
                'symbole': 'REPA',
                'description': 'Remplacement des arbres morts ou malades',
                'productivite_theorique': 3,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Replantation des palmiers',
                'symbole': 'REPP',
                'description': 'Remplacement des palmiers morts ou malades',
                'productivite_theorique': 3,
                'unite_productivite': 'palmiers'
            },
            {
                'nom_tache': 'Replantation des arbustes',
                'symbole': 'REPB',
                'description': 'Remplacement des arbustes morts ou malades',
                'productivite_theorique': 7,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Replantation des vivaces',
                'symbole': 'REPV',
                'description': 'Remplacement des vivaces mortes ou malades',
                'productivite_theorique': 15,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Replantation des graminées',
                'symbole': 'REPG',
                'description': 'Remplacement des graminées mortes ou malades',
                'productivite_theorique': 20,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Replantation des cactus',
                'symbole': 'REPC',
                'description': 'Remplacement des cactus morts ou malades',
                'productivite_theorique': 5,
                'unite_productivite': 'm2'
            },
            # ========== TAILLE DE FORMATION ==========
            {
                'nom_tache': 'Taille de formation',
                'symbole': 'TFO',
                'description': 'Taille pour donner une forme aux jeunes végétaux (surfaces)',
                'productivite_theorique': 7,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Taille de formation des arbres',
                'symbole': 'TFOA',
                'description': 'Taille de formation des arbres',
                'productivite_theorique': 2,
                'unite_productivite': 'arbres'
            },
            # ========== TAILLE D'ENTRETIEN ==========
            {
                'nom_tache': 'Taille d\'entretien des arbres',
                'symbole': 'TENA',
                'description': 'Taille régulière des arbres pour maintenir la forme et la santé',
                'productivite_theorique': 2,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Taille d\'entretien des arbustes',
                'symbole': 'TENB',
                'description': 'Taille régulière des arbustes',
                'productivite_theorique': 5,
                'unite_productivite': 'm2'
            },
            # ========== TAILLE DE RAJEUNISSEMENT/RÉGÉNÉRATION ==========
            {
                'nom_tache': 'Taille de rajeunissement',
                'symbole': 'TRAJ',
                'description': 'Taille sévère pour régénérer les végétaux âgés ou dégradés',
                'productivite_theorique': 3,
                'unite_productivite': 'm2'
            },
            # ========== TAILLE D'ÉCLAIRCISSAGE ==========
            {
                'nom_tache': 'Taille d\'éclaircissage',
                'symbole': 'TECL',
                'description': 'Suppression des branches pour aérer et améliorer la lumière',
                'productivite_theorique': 2,
                'unite_productivite': 'arbres'
            },
            # ========== TAILLE DÉCORATIVE/ORNEMENTALE ==========
            {
                'nom_tache': 'Taille décorative',
                'symbole': 'TDEC',
                'description': 'Taille artistique pour donner une forme ornementale (topiaire)',
                'productivite_theorique': 1,
                'unite_productivite': 'arbres'
            },
            # ========== TERREAUTAGE ==========
            {
                'nom_tache': 'Terreautage',
                'symbole': 'TER',
                'description': 'Apport de terreau pour enrichir le sol (surfaces)',
                'productivite_theorique': 37,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Terreautage des arbres',
                'symbole': 'TERA',
                'description': 'Terreautage autour des arbres',
                'productivite_theorique': 6,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Terreautage des palmiers',
                'symbole': 'TERP',
                'description': 'Terreautage autour des palmiers',
                'productivite_theorique': 6,
                'unite_productivite': 'palmiers'
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
                'productivite_theorique': 150,
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
                'nom_tache': 'Tonte rasée',
                'symbole': 'TONR',
                'description': 'Tonte très courte du gazon',
                'productivite_theorique': 800,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Sursemis',
                'symbole': 'SUR',
                'description': 'Semis complémentaire pour régénérer le gazon',
                'productivite_theorique': 600,
                'unite_productivite': 'm2'
            },
            # ========== RAMASSAGE DES DÉCHETS VERTS ==========
            {
                'nom_tache': 'Ramassage des déchets verts',
                'symbole': 'RAM',
                'description': 'Collecte et évacuation des déchets végétaux (surfaces)',
                'productivite_theorique': 56,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Ramassage des déchets verts des arbres',
                'symbole': 'RAMA',
                'description': 'Ramassage des déchets verts autour des arbres',
                'productivite_theorique': 10,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Ramassage des déchets verts des palmiers',
                'symbole': 'RAMP',
                'description': 'Ramassage des déchets verts autour des palmiers',
                'productivite_theorique': 6,
                'unite_productivite': 'palmiers'
            },
            # ========== DÉSHERBAGE ==========
            {
                'nom_tache': 'Désherbage manuel des arbres',
                'symbole': 'DEMA',
                'description': 'Désherbage manuel autour des arbres',
                'productivite_theorique': 30,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Désherbage manuel des palmiers',
                'symbole': 'DEMP',
                'description': 'Désherbage manuel autour des palmiers',
                'productivite_theorique': 30,
                'unite_productivite': 'palmiers'
            },
            {
                'nom_tache': 'Désherbage manuel des arbustes',
                'symbole': 'DEMB',
                'description': 'Désherbage manuel autour des arbustes',
                'productivite_theorique': 15,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Désherbage manuel des vivaces',
                'symbole': 'DEMV',
                'description': 'Désherbage manuel autour des vivaces',
                'productivite_theorique': 15,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Désherbage manuel des graminées',
                'symbole': 'DEMG',
                'description': 'Désherbage manuel autour des graminées',
                'productivite_theorique': 15,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Désherbage manuel des cactus',
                'symbole': 'DEMC',
                'description': 'Désherbage manuel autour des cactus',
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
            # ========== TRAÇAGE DES BORDURES ==========
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
                'productivite_theorique': 25,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrachage des graminées mortes',
                'symbole': 'AGM',
                'description': 'Extraction des graminées mortes',
                'productivite_theorique': 30,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrachage des cactus morts',
                'symbole': 'ACM',
                'description': 'Extraction des cactus morts',
                'productivite_theorique': 15,
                'unite_productivite': 'm2'
            },
            {
                'nom_tache': 'Arrachage des vivaces mortes',
                'symbole': 'AVM',
                'description': 'Extraction des vivaces mortes',
                'productivite_theorique': 20,
                'unite_productivite': 'm2'
            },
            # ========== APPORT DE TERRE ==========
            {
                'nom_tache': 'Apport de terre végétale',
                'symbole': 'ATV',
                'description': 'Apport de terre végétale pour améliorer la qualité du sol',
                'productivite_theorique': None,
                'unite_productivite': 'm3'
            },
            # ========== ENTRETIEN POTS INTÉRIEURS ==========
            {
                'nom_tache': 'Entretien des pots intérieurs',
                'symbole': 'EPI',
                'description': 'Entretien général des plantes en pots à l\'intérieur',
                'productivite_theorique': 20,
                'unite_productivite': 'pots'
            },
            {
                'nom_tache': 'Arrosage des pots intérieurs',
                'symbole': 'API',
                'description': 'Arrosage des plantes en pots à l\'intérieur',
                'productivite_theorique': 40,
                'unite_productivite': 'pots'
            },
            {
                'nom_tache': 'Remplacement du substrat',
                'symbole': 'RSU',
                'description': 'Remplacement du terreau dans les pots',
                'productivite_theorique': 10,
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
            # ========== DÉCORTICAGE (PALMIERS) ==========
            {
                'nom_tache': 'Décorticage des palmiers',
                'symbole': 'DCP',
                'description': 'Retrait des gaines foliaires sèches sur le stipe des palmiers',
                'productivite_theorique': 2,
                'unite_productivite': 'palmiers'
            },
            # ========== PALISSAGE ==========
            {
                'nom_tache': 'Palissage',
                'symbole': 'PAL',
                'description': 'Guidage et attache des plantes grimpantes sur des supports',
                'productivite_theorique': 10,
                'unite_productivite': 'm2'
            },
            # ========== PLANTATION ==========
            {
                'nom_tache': 'Plantation',
                'symbole': 'PLA',
                'description': 'Mise en terre de nouveaux végétaux',
                'productivite_theorique': 5,
                'unite_productivite': 'unite'
            },
            {
                'nom_tache': 'Plantation des arbres',
                'symbole': 'PLAA',
                'description': 'Plantation de nouveaux arbres',
                'productivite_theorique': 3,
                'unite_productivite': 'arbres'
            },
            {
                'nom_tache': 'Plantation des palmiers',
                'symbole': 'PLAP',
                'description': 'Plantation de nouveaux palmiers',
                'productivite_theorique': 2,
                'unite_productivite': 'palmiers'
            },
            {
                'nom_tache': 'Plantation des arbustes',
                'symbole': 'PLAB',
                'description': 'Plantation de nouveaux arbustes',
                'productivite_theorique': 10,
                'unite_productivite': 'm2'
            },
            # ========== MASTICAGE ==========
            {
                'nom_tache': 'Masticage',
                'symbole': 'MAS',
                'description': 'Application de mastic cicatrisant après taille ou blessure',
                'productivite_theorique': 15,
                'unite_productivite': 'arbres'
            },
            # ========== MULTIPLICATION VÉGÉTATIVE ==========
            {
                'nom_tache': 'Multiplication végétative',
                'symbole': 'MUL',
                'description': 'Bouturage, marcottage ou division pour multiplier les plantes',
                'productivite_theorique': 20,
                'unite_productivite': 'unite'
            },
            # ========== PINCEMENT ==========
            {
                'nom_tache': 'Pincement',
                'symbole': 'PIN',
                'description': 'Suppression des extrémités de tiges pour favoriser la ramification',
                'productivite_theorique': 50,
                'unite_productivite': 'm2'
            },
            # ========== ÉLIMINATION DES DRAGEONS ==========
            {
                'nom_tache': 'Élimination des drageons',
                'symbole': 'EDR',
                'description': 'Suppression des rejets indésirables à la base des végétaux',
                'productivite_theorique': 20,
                'unite_productivite': 'arbres'
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
