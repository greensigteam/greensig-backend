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

        # Matrice d'applicabilité
        # Format: nom_tache: liste des types d'objets applicables
        # Le ratio utilisé est celui de la productivité théorique du TypeTache
        APPLICABILITE = {
            # Tâches applicables à tous les végétaux
            'Nettoyage': TYPES_VEGETATION,
            'Binage': TYPES_VEGETATION,
            'Confection cuvette': TYPES_VEGETATION,
            'Traitement': TYPES_VEGETATION,
            'Arrosage': TYPES_VEGETATION,
            'Sablage': TYPES_VEGETATION,
            'Fertilisation': TYPES_VEGETATION,
            'Paillage': TYPES_VEGETATION,
            'Nivellement du sol': TYPES_VEGETATION,
            'Aération des sols': TYPES_VEGETATION,
            'Replantation': TYPES_VEGETATION,
            'Taille d\'entretien': TYPES_VEGETATION,
            'Terreautage': TYPES_VEGETATION,
            'Ramassage des déchets verts': TYPES_VEGETATION,
            'Désherbage': TYPES_VEGETATION,
            'Nivellement des bordures': TYPES_VEGETATION,
            'Arrachage des plantes mortes': TYPES_VEGETATION,

            # Tâches avec applicabilité restreinte
            'Élagage': ['Palmier', 'Arbre', 'Arbuste'],
            'Tuteurage': ['Palmier', 'Arbre', 'Arbuste', 'Vivace', 'Cactus'],
            'Taille de formation': ['Arbre', 'Arbuste', 'Vivace'],
            'Scarification': ['Graminee', 'Gazon'],
            'Tonte': ['Graminee', 'Gazon'],

            # Tâche hydraulique uniquement
            'Réparation des fuites': TYPES_HYDRAULIQUE,
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
