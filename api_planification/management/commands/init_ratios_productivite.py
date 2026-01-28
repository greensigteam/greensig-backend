"""
Management command pour initialiser les ratios de productivité et la matrice d'applicabilité.

Usage:
    python manage.py init_ratios_productivite
    python manage.py init_ratios_productivite --force  # Réinitialiser tous les ratios
"""
from django.core.management.base import BaseCommand
from api_planification.models import TypeTache, RatioProductivite


class Command(BaseCommand):
    help = 'Initialise les ratios de productivité (matrice d\'applicabilité tâche/type d\'objet)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Réinitialise les ratios même s\'ils existent déjà',
        )

    def handle(self, *args, **options):
        force = options['force']
        self.stdout.write('Initialisation des ratios de productivité...\n')

        # Types d'objets disponibles
        TYPES_VEGETATION = ['Palmier', 'Arbre', 'Arbuste', 'Vivace', 'Cactus', 'Graminee', 'Gazon']
        TYPES_HYDRAULIQUE = ['Puit', 'Pompe', 'Vanne', 'Clapet', 'Ballon', 'Canalisation', 'Aspersion', 'Goutte']

        # Matrice d'applicabilité basée sur le tableau de productivité théorique
        # Format: nom_tache: liste des types d'objets applicables
        # Basé sur le tableau Oui/Non fourni par l'utilisateur
        APPLICABILITE = {
            # ========== NETTOYAGE ==========
            'Nettoyage': TYPES_VEGETATION,
            'Nettoyage des arbres': ['Arbre'],
            'Nettoyage des palmiers': ['Palmier'],

            # ========== BINAGE ==========
            'Binage': ['Arbre', 'Arbuste', 'Vivace', 'Cactus', 'Graminee'],  # Pas Palmier ni Gazon
            'Binage des arbustes': ['Arbuste'],
            'Binage des vivaces': ['Vivace'],
            'Binage des cactus': ['Cactus'],
            'Binage des graminées': ['Graminee'],

            # ========== CONFECTION CUVETTE ==========
            'Confection cuvette': ['Palmier', 'Arbre', 'Arbuste'],  # Uniquement plantes ligneuses

            # ========== TRAITEMENT ==========
            'Traitement': TYPES_VEGETATION,
            'Traitement des arbres': ['Arbre'],
            'Traitement des palmiers': ['Palmier'],

            # ========== ARROSAGE ==========
            'Arrosage des arbres': ['Arbre'],
            'Arrosage des arbustes': ['Arbuste'],
            'Arrosage des palmiers': ['Palmier'],
            'Arrosage des graminées': ['Graminee'],
            'Arrosage des vivaces': ['Vivace'],
            'Arrosage des cactus': ['Cactus'],
            'Arrosage du gazon': ['Gazon'],

            # ========== ÉLAGAGE ==========
            'Élagage': ['Arbre', 'Arbuste'],  # Pas Palmier (voir Élagage des palmiers)
            'Élagage des palmiers': ['Palmier'],

            # ========== TUTEURAGE ==========
            'Tuteurage des arbres': ['Arbre'],
            'Tuteurage des palmiers': ['Palmier'],
            'Tuteurage des arbustes': ['Arbuste'],

            # ========== SABLAGE ==========
            # Le sablage s'applique uniquement au gazon
            'Sablage': ['Gazon'],

            # ========== FERTILISATION ==========
            'Fertilisation': TYPES_VEGETATION,
            'Fertilisation chimique': TYPES_VEGETATION,
            'Fertilisation organique': TYPES_VEGETATION,
            'Fertilisation des arbres': ['Arbre'],
            'Fertilisation des palmiers': ['Palmier'],

            # ========== PAILLAGE ==========
            'Paillage': ['Palmier', 'Arbre', 'Arbuste', 'Vivace', 'Cactus', 'Graminee'],  # Pas Gazon
            'Paillage des arbres': ['Arbre'],
            'Paillage des palmiers': ['Palmier'],

            # ========== NIVELLEMENT ==========
            'Nivellement du sol': TYPES_VEGETATION,

            # ========== AÉRATION DES SOLS ==========
            'Aération des sols pour gazon': ['Gazon'],

            # ========== REPLANTATION ==========
            'Replantation des arbres': ['Arbre'],
            'Replantation des palmiers': ['Palmier'],
            'Replantation des arbustes': ['Arbuste'],
            'Replantation des vivaces': ['Vivace'],
            'Replantation des graminées': ['Graminee'],
            'Replantation des cactus': ['Cactus'],

            # ========== TAILLE DE FORMATION ==========
            'Taille de formation': ['Arbre', 'Arbuste'],
            'Taille de formation des arbres': ['Arbre'],

            # ========== TAILLE D'ENTRETIEN ==========
            'Taille d\'entretien des arbres': ['Arbre'],
            'Taille d\'entretien des arbustes': ['Arbuste'],

            # ========== TAILLE DE RAJEUNISSEMENT ==========
            'Taille de rajeunissement': ['Arbre', 'Arbuste', 'Vivace'],

            # ========== TAILLE D'ÉCLAIRCISSAGE ==========
            'Taille d\'éclaircissage': ['Arbre', 'Arbuste'],

            # ========== TAILLE DÉCORATIVE ==========
            'Taille décorative': ['Arbre', 'Arbuste', 'Vivace'],

            # ========== TERREAUTAGE ==========
            'Terreautage': TYPES_VEGETATION,
            'Terreautage des arbres': ['Arbre'],
            'Terreautage des palmiers': ['Palmier'],

            # ========== ENTRETIEN GAZON ==========
            'Topdressing gazon': ['Gazon'],
            'Compactage du gazon': ['Gazon'],
            'Scarification': ['Gazon'],  # Uniquement gazon (pas graminées)
            'Tonte': ['Gazon'],  # Uniquement gazon
            'Tonte rasée': ['Gazon'],
            'Sursemis': ['Gazon'],

            # ========== RAMASSAGE DES DÉCHETS VERTS ==========
            'Ramassage des déchets verts': TYPES_VEGETATION,
            'Ramassage des déchets verts des arbres': ['Arbre'],
            'Ramassage des déchets verts des palmiers': ['Palmier'],

            # ========== DÉSHERBAGE ==========
            'Désherbage manuel des arbres': ['Arbre'],
            'Désherbage manuel des palmiers': ['Palmier'],
            'Désherbage manuel des arbustes': ['Arbuste'],
            'Désherbage manuel des vivaces': ['Vivace'],
            'Désherbage manuel des graminées': ['Graminee'],
            'Désherbage manuel des cactus': ['Cactus'],
            'Désherbage chimique': TYPES_VEGETATION,

            # ========== TRAÇAGE DES BORDURES ==========
            'Traçage des bordures': ['Gazon', 'Arbuste', 'Vivace', 'Graminee'],

            # ========== ARRACHAGE DES VÉGÉTAUX MORTS ==========
            'Arrachage des arbres morts': ['Arbre'],
            'Arrachage des palmiers morts': ['Palmier'],
            'Arrachage des arbustes morts': ['Arbuste'],
            'Arrachage des graminées mortes': ['Graminee'],
            'Arrachage des cactus morts': ['Cactus'],
            'Arrachage des vivaces mortes': ['Vivace'],

            # ========== APPORT DE TERRE ==========
            'Apport de terre végétale': TYPES_VEGETATION,

            # ========== ENTRETIEN POTS INTÉRIEURS ==========
            'Entretien des pots intérieurs': ['Arbuste', 'Vivace', 'Cactus', 'Graminee'],
            'Arrosage des pots intérieurs': ['Arbuste', 'Vivace', 'Cactus', 'Graminee'],
            'Remplacement du substrat': ['Arbuste', 'Vivace', 'Cactus', 'Graminee'],

            # ========== DÉCORTICAGE (PALMIERS UNIQUEMENT) ==========
            'Décorticage des palmiers': ['Palmier'],

            # ========== PALISSAGE ==========
            'Palissage': ['Arbuste', 'Vivace'],  # Plantes grimpantes

            # ========== PLANTATION ==========
            'Plantation': TYPES_VEGETATION,
            'Plantation des arbres': ['Arbre'],
            'Plantation des palmiers': ['Palmier'],
            'Plantation des arbustes': ['Arbuste'],

            # ========== MASTICAGE ==========
            'Masticage': ['Palmier', 'Arbre', 'Arbuste'],  # Après taille/blessure

            # ========== MULTIPLICATION VÉGÉTATIVE ==========
            'Multiplication végétative': ['Arbuste', 'Vivace', 'Graminee', 'Cactus'],

            # ========== PINCEMENT ==========
            'Pincement': ['Arbuste', 'Vivace'],

            # ========== ÉLIMINATION DES DRAGEONS ==========
            'Élimination des drageons': ['Palmier', 'Arbre', 'Arbuste'],

            # ========== HYDROLOGIE ==========
            'Réparation des fuites': TYPES_HYDRAULIQUE,
            'Contrôle du système d\'irrigation': TYPES_HYDRAULIQUE,
        }

        created_count = 0
        updated_count = 0
        skipped_count = 0
        not_found_types = []

        for task_type_name, applicable_objects in APPLICABILITE.items():
            # Rechercher le type de tâche
            try:
                type_tache = TypeTache.objects.get(nom_tache=task_type_name)
            except TypeTache.DoesNotExist:
                not_found_types.append(task_type_name)
                continue

            # Récupérer la productivité et l'unité du type de tâche
            ratio = type_tache.productivite_theorique or 1
            unite = type_tache.unite_productivite or 'unite'

            # Mapper les unités du TypeTache vers celles du RatioProductivite
            unite_mapping = {
                'm2': 'm2',
                'ml': 'ml',
                'unite': 'unite',
                'cuvettes': 'unite',
                'arbres': 'unite',
                'palmiers': 'unite',
                'pots': 'unite',
                'm3': 'm2',
            }
            unite_ratio = unite_mapping.get(unite, 'unite')

            for type_objet in applicable_objects:
                if force:
                    obj, created = RatioProductivite.objects.update_or_create(
                        id_type_tache=type_tache,
                        type_objet=type_objet,
                        defaults={
                            'ratio': ratio,
                            'unite_mesure': unite_ratio,
                            'actif': True,
                            'description': f'{type_tache.nom_tache} sur {type_objet} - {ratio} {unite}/h'
                        }
                    )
                    if created:
                        created_count += 1
                        self.stdout.write(f'  + {task_type_name} - {type_objet}: {ratio} {unite}/h')
                    else:
                        updated_count += 1
                        self.stdout.write(f'  ~ {task_type_name} - {type_objet}: {ratio} {unite}/h (mis à jour)')
                else:
                    obj, created = RatioProductivite.objects.get_or_create(
                        id_type_tache=type_tache,
                        type_objet=type_objet,
                        defaults={
                            'ratio': ratio,
                            'unite_mesure': unite_ratio,
                            'actif': True,
                            'description': f'{type_tache.nom_tache} sur {type_objet} - {ratio} {unite}/h'
                        }
                    )
                    if created:
                        created_count += 1
                        self.stdout.write(f'  + {task_type_name} - {type_objet}: {ratio} {unite}/h')
                    else:
                        skipped_count += 1

        # Résumé
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Ratios créés: {created_count}'))
        if force:
            self.stdout.write(self.style.WARNING(f'Ratios mis à jour: {updated_count}'))
        else:
            self.stdout.write(f'Ratios existants ignorés: {skipped_count}')

        if not_found_types:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'Types de tâches non trouvés (exécutez d\'abord seed_types_taches): {", ".join(not_found_types)}'
            ))

        # Afficher le récapitulatif de la matrice
        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write('MATRICE D\'APPLICABILITÉ:')
        self.stdout.write('=' * 60)

        for task_name, objects in APPLICABILITE.items():
            self.stdout.write(f'{task_name}: {", ".join(objects)}')

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Initialisation terminée!'))
        self.stdout.write('')
        self.stdout.write('Note: Pour vérifier l\'applicabilité d\'une tâche à un type d\'objet,')
        self.stdout.write('      utilisez RatioProductivite.objects.filter(id_type_tache=..., type_objet=...).exists()')
