from django.core.management.base import BaseCommand
from api_reclamations.models import TypeReclamation, Urgence


class Command(BaseCommand):
    help = 'Peuple les tables de référence pour le module Réclamations'

    def handle(self, *args, **options):
        self.stdout.write("Début du peuplement...")

        # 1. URGENCES
        urgences = [
            {'niveau_urgence': 'FAIBLE', 'couleur': '#2ecc71', 'ordre': 1},
            {'niveau_urgence': 'MOYENNE', 'couleur': '#f1c40f', 'ordre': 2},
            {'niveau_urgence': 'HAUTE', 'couleur': '#e67e22', 'ordre': 3},
            {'niveau_urgence': 'CRITIQUE', 'couleur': '#e74c3c', 'ordre': 4},
        ]

        urgences_created = 0
        for data in urgences:
            obj, created = Urgence.objects.get_or_create(
                niveau_urgence=data['niveau_urgence'],
                defaults=data
            )
            if created:
                urgences_created += 1
                self.stdout.write(self.style.SUCCESS(f'  Urgence créée: {obj}'))

        # 2. TYPES RECLAMATION
        types = [
            # URGENCE
            {'nom_reclamation': "Fuite d'eau", 'code_reclamation': 'URG-FUITE', 'categorie': 'URGENCE', 'symbole': '💧'},
            {'nom_reclamation': "Équipement en panne", 'code_reclamation': 'URG-PANNE', 'categorie': 'URGENCE', 'symbole': '⚠️'},

            # QUALITE
            {'nom_reclamation': "Végétation arrachée", 'code_reclamation': 'QLT-ARRACHEE', 'categorie': 'QUALITE', 'symbole': '🌿'},
            {'nom_reclamation': "Zone dégradée", 'code_reclamation': 'QLT-DEGRADEE', 'categorie': 'QUALITE', 'symbole': '📍'},
            {'nom_reclamation': "Manque entretien", 'code_reclamation': 'QLT-ENTRETIEN', 'categorie': 'QUALITE', 'symbole': '🔧'},
            {'nom_reclamation': "Maladie", 'code_reclamation': 'QLT-MALADIE', 'categorie': 'QUALITE', 'symbole': '🦠'},
            {'nom_reclamation': "Ravageur", 'code_reclamation': 'QLT-RAVAGEUR', 'categorie': 'QUALITE', 'symbole': '🐛'},
            {'nom_reclamation': "Plantes mortes", 'code_reclamation': 'QLT-MORTES', 'categorie': 'QUALITE', 'symbole': '🥀'},
            {'nom_reclamation': "Sol compacté", 'code_reclamation': 'QLT-SOL', 'categorie': 'QUALITE', 'symbole': '🪨'},
            {'nom_reclamation': "Accumulation de déchets verts", 'code_reclamation': 'QLT-DECHETS', 'categorie': 'QUALITE', 'symbole': '🍂'},

            # PLANNING
            {'nom_reclamation': "Zone à prioriser", 'code_reclamation': 'PLN-PRIORITE', 'categorie': 'PLANNING', 'symbole': '⭐'},
            {'nom_reclamation': "Évènement planifié", 'code_reclamation': 'PLN-EVENT', 'categorie': 'PLANNING', 'symbole': '📅'},
            {'nom_reclamation': "Retard des équipes", 'code_reclamation': 'PLN-RETARD', 'categorie': 'PLANNING', 'symbole': '⏰'},
            {'nom_reclamation': "Planning non respecté", 'code_reclamation': 'PLN-NONRESP', 'categorie': 'PLANNING', 'symbole': '📋'},

            # RESSOURCES
            {'nom_reclamation': "Manque matériel", 'code_reclamation': 'RES-MATERIEL', 'categorie': 'RESSOURCES', 'symbole': '🛠️'},
            {'nom_reclamation': "Manque effectif", 'code_reclamation': 'RES-EFFECTIF', 'categorie': 'RESSOURCES', 'symbole': '👷'},

            # AUTRE
            {'nom_reclamation': "Autre", 'code_reclamation': 'AUTRE-DIVERS', 'categorie': 'AUTRE', 'symbole': '📝'},
        ]

        types_created = 0
        for data in types:
            obj, created = TypeReclamation.objects.get_or_create(
                code_reclamation=data['code_reclamation'],
                defaults=data
            )
            if created:
                types_created += 1
                self.stdout.write(self.style.SUCCESS(f'  Type créé: {obj}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Peuplement terminé: {urgences_created} urgences, {types_created} types créés'
        ))
