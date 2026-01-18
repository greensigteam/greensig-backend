"""
Commande de seed pour les produits phytosanitaires, fertilisants et ravageurs/maladies.

Basé sur le dictionnaire de données ENJR_11_2025.

Usage:
    python manage.py seed_produits
    python manage.py seed_produits --force  # Réinitialise toutes les données
"""
from django.core.management.base import BaseCommand
from datetime import date
from decimal import Decimal
from api_suivi_taches.models import (
    Produit,
    ProduitMatiereActive,
    DoseProduit,
    Fertilisant,
    RavageurMaladie
)


class Command(BaseCommand):
    help = 'Seed les produits phytosanitaires, fertilisants et ravageurs/maladies depuis le dictionnaire de données'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Supprime et recrée toutes les données'
        )

    def handle(self, *args, **options):
        force = options.get('force', False)

        self.stdout.write(self.style.HTTP_INFO("=" * 80))
        self.stdout.write(self.style.HTTP_INFO("SEED PRODUITS - Dictionnaire de données ENJR"))
        self.stdout.write(self.style.HTTP_INFO("=" * 80))

        if force:
            self.stdout.write(self.style.WARNING("Mode --force: suppression des données existantes..."))
            RavageurMaladie.objects.all().delete()
            Fertilisant.objects.all().delete()
            DoseProduit.objects.all().delete()
            ProduitMatiereActive.objects.all().delete()
            Produit.objects.all().delete()

        # Étape 1: Produits phytosanitaires
        produits_map = self.seed_produits()

        # Étape 2: Fertilisants
        self.seed_fertilisants()

        # Étape 3: Ravageurs et maladies
        self.seed_ravageurs_maladies(produits_map)

        self.stdout.write(self.style.SUCCESS("=" * 80))
        self.stdout.write(self.style.SUCCESS("SEED TERMINÉ AVEC SUCCÈS"))
        self.stdout.write(self.style.SUCCESS("=" * 80))

    def seed_produits(self):
        """Crée les produits phytosanitaires avec matières actives et doses."""
        self.stdout.write(self.style.HTTP_INFO("\nÉTAPE 1: Produits phytosanitaires"))
        self.stdout.write("-" * 40)

        produits_data = [
            {
                'nom_produit': 'PYRISTAR',
                'numero_homologation': 'H07-1-014',
                'date_validite': date(2031, 10, 6),
                'cible': 'Cochenilles',
                'matieres_actives': [
                    {'matiere_active': 'Pyriproxyfène', 'teneur_valeur': Decimal('100'), 'teneur_unite': 'g/l'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('35'), 'dose_unite_produit': 'cc', 'dose_unite_support': 'hl', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'ABAMEC',
                'numero_homologation': 'E01-4-001',
                'date_validite': date(2032, 4, 6),
                'cible': 'Acariens',
                'matieres_actives': [
                    {'matiere_active': 'Abamectine', 'teneur_valeur': Decimal('18'), 'teneur_unite': 'g/l'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('50'), 'dose_unite_produit': 'cc', 'dose_unite_support': 'hl', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'JACKPOT 50 G/L EC',
                'numero_homologation': 'E11-7-015',
                'date_validite': date(2029, 12, 23),
                'cible': 'Pucerons',
                'matieres_actives': [
                    {'matiere_active': 'Lambda cyhalothrine', 'teneur_valeur': Decimal('50'), 'teneur_unite': 'g/l'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('100'), 'dose_unite_produit': 'cc', 'dose_unite_support': 'ha', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'AFESOUFRE VENTILÉ 98,5 % DP',
                'numero_homologation': 'F02-8-003',
                'date_validite': date(2030, 7, 21),
                'cible': 'Oïdium',
                'matieres_actives': [
                    {'matiere_active': 'Soufre', 'teneur_valeur': Decimal('98.5'), 'teneur_unite': '%'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('20'), 'dose_unite_produit': 'kg', 'dose_unite_support': 'ha', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'ACROBAT CU',
                'numero_homologation': 'F11-2-002',
                'date_validite': date(2027, 12, 27),
                'cible': 'Mildiou',
                'matieres_actives': [
                    {'matiere_active': 'Cuivre - oxychlorure de cuivre', 'teneur_valeur': Decimal('40'), 'teneur_unite': '%'},
                    {'matiere_active': 'Diméthomorphe', 'teneur_valeur': Decimal('6'), 'teneur_unite': '%'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('2.5'), 'dose_unite_produit': 'kg', 'dose_unite_support': 'ha', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'AFRO-CUIVRE 50 WP',
                'numero_homologation': 'H09-1-009',
                'date_validite': date(2031, 12, 23),
                'cible': 'Chancre',
                'matieres_actives': [
                    {'matiere_active': 'Oxyde de cuivre', 'teneur_valeur': Decimal('50'), 'teneur_unite': '%'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('300'), 'dose_unite_produit': 'g', 'dose_unite_support': 'hl', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'CUPROZIN PLUS',
                'numero_homologation': 'H09-1-009',
                'date_validite': date(2031, 6, 24),
                'cible': 'Moniliose',
                'matieres_actives': [
                    {'matiere_active': 'Cuivre - oxychlorure de cuivre', 'teneur_valeur': Decimal('50'), 'teneur_unite': '%'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('500'), 'dose_unite_produit': 'g', 'dose_unite_support': 'hl', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'PROLECTUS 50 WG',
                'numero_homologation': 'F03-3-008',
                'date_validite': date(2028, 7, 10),
                'cible': 'Botrytis',
                'matieres_actives': [
                    {'matiere_active': 'Fenpyrazamine', 'teneur_valeur': Decimal('50'), 'teneur_unite': '%'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('20'), 'dose_unite_produit': 'g', 'dose_unite_support': 'hl', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'CORAGEN',
                'numero_homologation': 'E12-9-001',
                'date_validite': date(2033, 10, 17),
                'cible': 'Ver du gazon',
                'matieres_actives': [
                    {'matiere_active': 'Chlorantraniliprole', 'teneur_valeur': Decimal('20'), 'teneur_unite': '%'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('200'), 'dose_unite_produit': 'cc', 'dose_unite_support': 'ha', 'contexte': ''}
                ]
            },
            {
                'nom_produit': 'ARDOR 21,4 SC',
                'numero_homologation': 'F05-8-004',
                'date_validite': date(2028, 6, 19),
                'cible': 'Thrips',
                'matieres_actives': [
                    {'matiere_active': 'Imidaclopride', 'teneur_valeur': Decimal('21.4'), 'teneur_unite': '%'}
                ],
                'doses': [
                    {'dose_valeur': Decimal('50'), 'dose_unite_produit': 'cc', 'dose_unite_support': 'hl', 'contexte': ''}
                ]
            },
        ]

        produits_map = {}
        created_count = 0
        updated_count = 0

        for data in produits_data:
            matieres = data.pop('matieres_actives')
            doses = data.pop('doses')

            produit, created = Produit.objects.update_or_create(
                nom_produit=data['nom_produit'],
                defaults=data
            )

            if created:
                created_count += 1
            else:
                updated_count += 1
                # Supprimer les anciennes matières actives et doses
                produit.matieres_actives.all().delete()
                produit.doses.all().delete()

            # Créer les matières actives
            for ordre, ma_data in enumerate(matieres, 1):
                ProduitMatiereActive.objects.create(
                    produit=produit,
                    ordre=ordre,
                    **ma_data
                )

            # Créer les doses
            for dose_data in doses:
                DoseProduit.objects.create(
                    produit=produit,
                    **dose_data
                )

            produits_map[produit.nom_produit] = produit
            status = "[+]" if created else "[~]"
            self.stdout.write(f"  {status} {produit.nom_produit}")

        self.stdout.write(self.style.SUCCESS(f"  => {created_count} crees, {updated_count} mis a jour"))
        return produits_map

    def seed_fertilisants(self):
        """Crée les fertilisants."""
        self.stdout.write(self.style.HTTP_INFO("\nÉTAPE 2: Fertilisants"))
        self.stdout.write("-" * 40)

        fertilisants_data = [
            {'nom': 'Engrais NPK', 'type_fertilisant': 'CHIMIQUE', 'format_fertilisant': 'GRANULE'},
            {'nom': 'Engrais NPK', 'type_fertilisant': 'CHIMIQUE', 'format_fertilisant': 'LIQUIDE'},
            {'nom': 'Engrais NPK', 'type_fertilisant': 'CHIMIQUE', 'format_fertilisant': 'POUDRE'},
            {'nom': 'Compost', 'type_fertilisant': 'ORGANIQUE', 'format_fertilisant': 'SOLIDE'},
            {'nom': 'Compost', 'type_fertilisant': 'ORGANIQUE', 'format_fertilisant': 'DECOMPOSE'},
            {'nom': 'Terreau', 'type_fertilisant': 'SUBSTRAT', 'format_fertilisant': 'SOLIDE'},
            {'nom': 'Sablage', 'type_fertilisant': 'MINERAL', 'format_fertilisant': 'SOLIDE'},
            {'nom': 'Biostimulant', 'type_fertilisant': 'BIOLOGIQUE', 'format_fertilisant': 'LIQUIDE'},
            {'nom': 'Biostimulant', 'type_fertilisant': 'BIOLOGIQUE', 'format_fertilisant': 'POUDRE'},
            {'nom': 'Biostimulant', 'type_fertilisant': 'ORGANIQUE', 'format_fertilisant': 'LIQUIDE'},
            {'nom': 'Biostimulant', 'type_fertilisant': 'ORGANIQUE', 'format_fertilisant': 'POUDRE'},
        ]

        created_count = 0
        for data in fertilisants_data:
            fertilisant, created = Fertilisant.objects.get_or_create(
                nom=data['nom'],
                type_fertilisant=data['type_fertilisant'],
                format_fertilisant=data['format_fertilisant'],
                defaults={'actif': True}
            )
            if created:
                created_count += 1
                self.stdout.write(f"  [+] {fertilisant}")

        self.stdout.write(self.style.SUCCESS(f"  => {created_count} fertilisants crees"))

    def seed_ravageurs_maladies(self, produits_map):
        """Crée les ravageurs et maladies avec leurs produits recommandés."""
        self.stdout.write(self.style.HTTP_INFO("\nÉTAPE 3: Ravageurs et Maladies"))
        self.stdout.write("-" * 40)

        ravageurs_data = [
            {
                'nom': 'Mildiou',
                'categorie': 'MALADIE',
                'symptomes': 'Apparition de moisissures grisâtres ou blanchâtres',
                'partie_atteinte': 'Feuilles',
                'produits': ['ACROBAT CU']
            },
            {
                'nom': 'Oïdium',
                'categorie': 'MALADIE',
                'symptomes': 'Poudre blanche ou grisâtre',
                'partie_atteinte': 'Tiges, fleurs, feuilles',
                'produits': ['AFESOUFRE VENTILÉ 98,5 % DP']
            },
            {
                'nom': 'Chancre',
                'categorie': 'MALADIE',
                'symptomes': 'Nécroses, suintements, crevasses sur l\'écorce, dessèchement des rameaux',
                'partie_atteinte': 'Écorce',
                'produits': ['AFRO-CUIVRE 50 WP']
            },
            {
                'nom': 'Moniliose',
                'categorie': 'MALADIE',
                'symptomes': 'Fruits momifiés accrochés (nécrosés) et sporulation poudreuse sur fruits',
                'partie_atteinte': 'Fruits',
                'produits': ['CUPROZIN PLUS']
            },
            {
                'nom': 'Botrytis',
                'categorie': 'MALADIE',
                'symptomes': 'Feutrage gris, taches brunes, pourriture des fleurs et feuilles',
                'partie_atteinte': 'Fleurs, feuilles',
                'produits': ['PROLECTUS 50 WG']
            },
            {
                'nom': 'Cochenilles',
                'categorie': 'RAVAGEUR',
                'symptomes': 'Présence d\'un écusson cireux/rigide fixé sur le végétal',
                'partie_atteinte': 'Feuilles',
                'produits': ['PYRISTAR']
            },
            {
                'nom': 'Ver du gazon',
                'categorie': 'RAVAGEUR',
                'symptomes': 'Jaunissement, zones clairsemées, plaques de gazon qui se soulèvent',
                'partie_atteinte': 'Racines',
                'produits': ['CORAGEN']
            },
            {
                'nom': 'Thrips',
                'categorie': 'RAVAGEUR',
                'symptomes': 'Déformations, ponctuations noires et décolorations argentées sur feuilles',
                'partie_atteinte': 'Feuilles',
                'produits': ['ARDOR 21,4 SC']
            },
            {
                'nom': 'Pucerons',
                'categorie': 'RAVAGEUR',
                'symptomes': 'Amas de petits insectes mous, déformation de jeunes pousses, fumagine et miellat',
                'partie_atteinte': 'Feuilles',
                'produits': ['JACKPOT 50 G/L EC']
            },
            {
                'nom': 'Acariens',
                'categorie': 'RAVAGEUR',
                'symptomes': 'Pointillés de succion (punctures) très réguliers et parfois toile fine sur l\'envers des feuilles',
                'partie_atteinte': 'Feuilles',
                'produits': ['ABAMEC']
            },
        ]

        created_count = 0
        for data in ravageurs_data:
            produits_noms = data.pop('produits')

            ravageur, created = RavageurMaladie.objects.get_or_create(
                nom=data['nom'],
                defaults={
                    'categorie': data['categorie'],
                    'symptomes': data['symptomes'],
                    'partie_atteinte': data['partie_atteinte'],
                    'actif': True
                }
            )

            if created:
                created_count += 1
                # Ajouter les produits recommandés
                for nom_produit in produits_noms:
                    produit = produits_map.get(nom_produit)
                    if produit:
                        ravageur.produits_recommandes.add(produit)
                self.stdout.write(f"  [+] {ravageur.nom} ({ravageur.get_categorie_display()})")

        self.stdout.write(self.style.SUCCESS(f"  => {created_count} ravageurs/maladies crees"))
