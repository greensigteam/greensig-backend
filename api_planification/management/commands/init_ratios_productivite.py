"""
Management command pour initialiser les ratios de productivité par défaut.

Usage:
    python manage.py init_ratios_productivite
    python manage.py init_ratios_productivite --force  # Réinitialiser tous les ratios
"""
from django.core.management.base import BaseCommand
from api_planification.models import TypeTache, RatioProductivite


class Command(BaseCommand):
    help = 'Initialise les ratios de productivité par défaut pour le calcul de charge'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Réinitialise les ratios même s\'ils existent déjà',
        )

    def handle(self, *args, **options):
        force = options['force']
        self.stdout.write('Initialisation des ratios de productivité...\n')

        # Matrice des ratios par défaut
        # Format: {nom_type_tache: {type_objet: (ratio, unite_mesure)}}
        DEFAULT_RATIOS = {
            'Tonte': {
                'Gazon': (500, 'm2'),      # 500 m²/h avec tondeuse autoportée
                'Graminee': (400, 'm2'),   # 400 m²/h
            },
            'Taille': {
                'Arbre': (4, 'unite'),     # 4 arbres/h pour taille légère
                'Palmier': (3, 'unite'),   # 3 palmiers/h
                'Arbuste': (200, 'm2'),    # 200 m²/h de massifs
                'Vivace': (300, 'm2'),     # 300 m²/h
                'Cactus': (150, 'm2'),     # 150 m²/h
            },
            'Désherbage': {
                'Gazon': (100, 'm2'),      # 100 m²/h désherbage manuel
                'Arbuste': (80, 'm2'),
                'Vivace': (100, 'm2'),
                'Graminee': (100, 'm2'),
            },
            'Arrosage': {
                'Gazon': (1000, 'm2'),     # 1000 m²/h avec système automatique
                'Arbuste': (500, 'm2'),
                'Arbre': (20, 'unite'),    # 20 arbres/h arrosage manuel
                'Palmier': (15, 'unite'),
            },
            'Élagage': {
                'Arbre': (2, 'unite'),     # 2 arbres/h (travail intensif)
                'Palmier': (1.5, 'unite'), # 1.5 palmiers/h
            },
            'Inspection irrigation': {
                'Canalisation': (200, 'ml'),  # 200 m linéaires/h
                'Aspersion': (150, 'ml'),
                'Goutte': (100, 'ml'),
                'Vanne': (15, 'unite'),       # 15 vannes/h
                'Pompe': (4, 'unite'),
                'Puit': (3, 'unite'),
            },
            'Maintenance pompes': {
                'Pompe': (2, 'unite'),        # 2 pompes/h maintenance préventive
                'Ballon': (3, 'unite'),
            },
            'Nettoyage général': {
                'Gazon': (800, 'm2'),         # 800 m²/h ramassage feuilles
                'Arbuste': (400, 'm2'),
            },
            'Traitement phytosanitaire': {
                'Arbre': (10, 'unite'),       # 10 arbres/h pulvérisation
                'Palmier': (8, 'unite'),
                'Arbuste': (300, 'm2'),
                'Gazon': (600, 'm2'),
            },
            'Plantation': {
                'Arbre': (2, 'unite'),        # 2 arbres/h (préparation + plantation)
                'Palmier': (1.5, 'unite'),
                'Arbuste': (50, 'm2'),
                'Vivace': (100, 'm2'),
                'Gazon': (200, 'm2'),         # Engazonnement
            },
        }

        created_count = 0
        updated_count = 0
        skipped_count = 0
        not_found_types = []

        for task_type_name, object_ratios in DEFAULT_RATIOS.items():
            # Rechercher le type de tâche (insensible à la casse)
            try:
                type_tache = TypeTache.objects.get(nom_tache__iexact=task_type_name)
            except TypeTache.DoesNotExist:
                not_found_types.append(task_type_name)
                continue

            for type_objet, (ratio, unite) in object_ratios.items():
                if force:
                    obj, created = RatioProductivite.objects.update_or_create(
                        id_type_tache=type_tache,
                        type_objet=type_objet,
                        defaults={
                            'ratio': ratio,
                            'unite_mesure': unite,
                            'actif': True,
                            'description': f'Ratio par défaut - {ratio} {unite}/h'
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
                            'unite_mesure': unite,
                            'actif': True,
                            'description': f'Ratio par défaut - {ratio} {unite}/h'
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
                f'Types de tâches non trouvés (à créer si nécessaire): {", ".join(not_found_types)}'
            ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Initialisation terminée!'))
