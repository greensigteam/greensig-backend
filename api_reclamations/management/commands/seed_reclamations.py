from django.core.management.base import BaseCommand
from api_reclamations.models import TypeReclamation, Urgence

class Command(BaseCommand):
    help = 'Peuple les tables de référence pour le module Réclamations'

    def handle(self, *args, **options):
        self.stdout.write("Début du peuplement...")

        # 1. URGENCES
        urgences = [
            {'niveau_urgence': 'FAIBLE', 'couleur': '#2ecc71', 'delai_max_traitement': 72, 'ordre': 1},
            {'niveau_urgence': 'MOYENNE', 'couleur': '#f1c40f', 'delai_max_traitement': 24, 'ordre': 2},
            {'niveau_urgence': 'HAUTE', 'couleur': '#e67e22', 'delai_max_traitement': 8, 'ordre': 3},
            {'niveau_urgence': 'CRITIQUE', 'couleur': '#e74c3c', 'delai_max_traitement': 2, 'ordre': 4},
        ]
        
        for data in urgences:
            obj, created = Urgence.objects.get_or_create(
                niveau_urgence=data['niveau_urgence'],
                defaults=data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Urgence créée: {obj}'))

        # 2. TYPES RECLAMATION
        types = [
            # URGENCE
            {'nom_reclamation': "Fuite d'irrigation majeure", 'code_reclamation': 'URG-FUITE', 'categorie': 'URGENCE'},
            {'nom_reclamation': "Arbre dangereux / Chute de branche", 'code_reclamation': 'URG-ARBRE', 'categorie': 'URGENCE'},
            {'nom_reclamation': "Panne station pompage", 'code_reclamation': 'URG-POMPE', 'categorie': 'URGENCE'},
            
            # QUALITE
            {'nom_reclamation': "Tonte non conforme", 'code_reclamation': 'QLT-TONTE', 'categorie': 'QUALITE'},
            {'nom_reclamation': "Taille non effectuée", 'code_reclamation': 'QLT-TAILLE', 'categorie': 'QUALITE'},
            {'nom_reclamation': "Mauvais désherbage", 'code_reclamation': 'QLT-DESHERB', 'categorie': 'QUALITE'},
            {'nom_reclamation': "Propreté / Déchets verts", 'code_reclamation': 'QLT-DECHETS', 'categorie': 'QUALITE'},
            
            # PLANNING
            {'nom_reclamation': "Prestation non réalisée", 'code_reclamation': 'PLN-ABSENCE', 'categorie': 'PLANNING'},
            {'nom_reclamation': "Retard intervention", 'code_reclamation': 'PLN-RETARD', 'categorie': 'PLANNING'},
            
            # RESSOURCES / AUTRE
            {'nom_reclamation': "Comportement équipe", 'code_reclamation': 'RH-COMP', 'categorie': 'RESSOURCES'},
            {'nom_reclamation': "Autre demande", 'code_reclamation': 'AUTRE', 'categorie': 'AUTRE'},
        ]

        for data in types:
            obj, created = TypeReclamation.objects.get_or_create(
                code_reclamation=data['code_reclamation'],
                defaults=data
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Type créé: {obj}'))

        self.stdout.write(self.style.SUCCESS("Peuplement terminé avec succès !"))
