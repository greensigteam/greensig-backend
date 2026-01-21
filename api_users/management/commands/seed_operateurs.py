from django.core.management.base import BaseCommand
from api_users.models import (
    Operateur, Equipe, Competence, CompetenceOperateur,
    StatutOperateur, NiveauCompetence, CategorieCompetence
)
from datetime import date


class Command(BaseCommand):
    help = 'Peuple la base de données avec les opérateurs, équipes et compétences'

    def normaliser_niveau(self, valeur):
        """Convertit les valeurs textuelles en NiveauCompetence."""
        if not valeur or valeur.strip() == '':
            return NiveauCompetence.NON

        valeur_lower = valeur.lower().strip()
        mapping = {
            'non': NiveauCompetence.NON,
            'débutant': NiveauCompetence.DEBUTANT,
            'debutant': NiveauCompetence.DEBUTANT,
            'intermédiaire': NiveauCompetence.INTERMEDIAIRE,
            'intermediaire': NiveauCompetence.INTERMEDIAIRE,
            'expert': NiveauCompetence.EXPERT,
            'oui': NiveauCompetence.DEBUTANT,  # "oui" → débutant par défaut
        }
        return mapping.get(valeur_lower, NiveauCompetence.NON)

    def handle(self, *args, **options):
        self.stdout.write("Début du peuplement des opérateurs, équipes et compétences...")
        self.stdout.write("")

        # ====================================================================
        # ÉTAPE 1: Créer les compétences
        # ====================================================================
        self.stdout.write(self.style.HTTP_INFO("ÉTAPE 1: Création des compétences"))

        competences_data = [
            ('Gestion d\'équipe', CategorieCompetence.ORGANISATIONNELLE),
            ('Tondeuse', CategorieCompetence.TECHNIQUE),
            ('Débroussailleuse', CategorieCompetence.TECHNIQUE),
            ('Tronçonneuse', CategorieCompetence.TECHNIQUE),
            ('Désherbage', CategorieCompetence.TECHNIQUE),
            ('Binage', CategorieCompetence.TECHNIQUE),
            ('Confection des cuvettes', CategorieCompetence.TECHNIQUE),
            ('Taille de nettoyage', CategorieCompetence.TECHNIQUE),
            ('Taille de décoration', CategorieCompetence.TECHNIQUE),
            ('Arrosage', CategorieCompetence.TECHNIQUE),
            ('Elagage de palmiers', CategorieCompetence.TECHNIQUE),
            ('Nettoyage général', CategorieCompetence.TECHNIQUE),
            ('Voiture', CategorieCompetence.TECHNIQUE),
            ('Camion', CategorieCompetence.TECHNIQUE),
            ('Nacelle', CategorieCompetence.TECHNIQUE),
            ('Grue', CategorieCompetence.TECHNIQUE),
            ('Plomberie', CategorieCompetence.TECHNIQUE),
            ('Electricité', CategorieCompetence.TECHNIQUE),
            ('Traitement phytosanitaire', CategorieCompetence.TECHNIQUE),
        ]

        competences_map = {}
        for nom, categorie in competences_data:
            comp, created = Competence.objects.get_or_create(
                nom_competence=nom,
                defaults={'categorie': categorie, 'description': f'Compétence: {nom}'}
            )
            competences_map[nom] = comp
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Compétence créée: {nom}'))
            else:
                self.stdout.write(f'  Compétence existante: {nom}')

        # ====================================================================
        # ÉTAPE 2: Créer les équipes
        # ====================================================================
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("ÉTAPE 2: Création des équipes"))

        noms_equipes = [
            'V.CT1', 'V.M ESPACE COMMUN', 'E.M.PHENO', 'V.CT2', 'T.PARK',
            'V.M ARROSAGE', 'V.M 83 à 76', 'CUB', 'V.M 31 à 34, 93 à 96',
            'H.HILTON', 'SUPPLEANT', 'V.M 26 à 30, 65 et 66', 'V.M 67 à 75',
            'S.G.DICE', 'R.LOCATIVES', 'V.M TONTE', 'V.M 9 à 15, 49 à 52',
            'V.M 41 à 48', 'V.M 21 à 25', 'V.M 57 à 64', 'V.M 84 à 92',
            'V.M 97 à 103', 'V.M 1 à 8, 105 et 42', 'V.M 35 à 40, 104 et 70',
            'V.M 16 à 20 et 53 à 56', 'TECH ARROSAGE', 'Hilton'
        ]

        equipes_map = {}
        for nom in noms_equipes:
            equipe, created = Equipe.objects.get_or_create(
                nom_equipe=nom,
                defaults={'actif': True, 'date_creation': date.today()}
            )
            equipes_map[nom] = equipe
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Équipe créée: {nom}'))
            else:
                self.stdout.write(f'  Équipe existante: {nom}')

        # ====================================================================
        # ÉTAPE 3: Créer les opérateurs avec compétences
        # ====================================================================
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("ÉTAPE 3: Import des opérateurs"))

        # Données des opérateurs avec compétences détaillées
        operateurs_data = [
            {
                'matricule': '2', 'prenom': 'JILALI', 'nom': 'ESSADDIQI', 'equipe': 'V.CT1', 'remarque': 'chef d\'équipe',
                'competences': {
                    'Gestion d\'équipe': 'intermédiaire', 'Tronçonneuse': 'débutant', 'Désherbage': 'expert',
                    'Binage': 'expert', 'Confection des cuvettes': 'expert', 'Taille de nettoyage': 'intermédiaire',
                    'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '3', 'prenom': 'MOHAMMED', 'nom': 'LAABIDI', 'equipe': 'V.M ESPACE COMMUN', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Tronçonneuse': 'débutant', 'Désherbage': 'intermédiaire',
                    'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire', 'Taille de nettoyage': 'intermédiaire',
                    'Taille de décoration': 'débutant', 'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire', 'Voiture': 'oui'
                }
            },
            {
                'matricule': '4', 'prenom': 'AHMED', 'nom': 'ENADIFI', 'equipe': 'E.M.PHENO', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Débroussailleuse': 'intermédiaire', 'Tronçonneuse': 'débutant',
                    'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'débutant', 'Arrosage': 'intermédiaire',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire', 'Camion': 'oui', 'Electricité': 'oui'
                }
            },
            {
                'matricule': '5', 'prenom': 'MOUHCINE', 'nom': 'GLIYA', 'equipe': 'V.CT2', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire',
                    'Confection des cuvettes': 'débutant', 'Taille de nettoyage': 'débutant', 'Taille de décoration': 'débutant',
                    'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'débutant',
                    'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '7', 'prenom': 'RACHID', 'nom': 'EL MASKAOUI', 'equipe': 'T.PARK', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire',
                    'Confection des cuvettes': 'intermédiaire', 'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'débutant',
                    'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '8', 'prenom': 'EL GHAZOUANI', 'nom': 'EL MAATAOUI', 'equipe': 'V.M ESPACE COMMUN', 'remarque': 'Jardinier',
                'competences': {
                    'Gestion d\'équipe': 'intermédiaire', 'Tondeuse': 'intermédiaire', 'Débroussailleuse': 'intermédiaire',
                    'Tronçonneuse': 'intermédiaire', 'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'expert', 'Taille de décoration': 'expert', 'Arrosage': 'expert',
                    'Elagage de palmiers': 'expert', 'Nettoyage général': 'expert'
                }
            },
            {
                'matricule': '9', 'prenom': 'HMED', 'nom': 'AZOUZI', 'equipe': 'E.M.PHENO', 'remarque': 'Caporal',
                'competences': {
                    'Gestion d\'équipe': 'débutant', 'Tondeuse': 'débutant', 'Débroussailleuse': 'intermédiaire',
                    'Tronçonneuse': 'débutant', 'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire',
                    'Confection des cuvettes': 'intermédiaire', 'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire',
                    'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire',
                    'Voiture': 'oui', 'Nacelle': 'oui'
                }
            },
            {
                'matricule': '10', 'prenom': 'ABDELILAH', 'nom': 'MARZAK', 'equipe': 'V.M ARROSAGE', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire',
                    'Confection des cuvettes': 'intermédiaire', 'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire',
                    'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire',
                    'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '11', 'prenom': 'JAMAL', 'nom': 'BENMAATI', 'equipe': 'V.M 83 à 76', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Tronçonneuse': 'débutant', 'Désherbage': 'intermédiaire',
                    'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire', 'Taille de nettoyage': 'intermédiaire',
                    'Taille de décoration': 'intermédiaire', 'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire', 'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '12', 'prenom': 'RACHID', 'nom': 'MAHD', 'equipe': 'T.PARK', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Tronçonneuse': 'débutant', 'Désherbage': 'expert',
                    'Binage': 'expert', 'Confection des cuvettes': 'expert', 'Taille de nettoyage': 'intermédiaire',
                    'Taille de décoration': 'débutant', 'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '15', 'prenom': 'HOUSSINE', 'nom': 'MOUTASSADDIQ', 'equipe': 'CUB', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Tronçonneuse': 'débutant', 'Désherbage': 'expert',
                    'Binage': 'expert', 'Confection des cuvettes': 'expert', 'Taille de nettoyage': 'intermédiaire',
                    'Taille de décoration': 'intermédiaire', 'Arrosage': 'expert', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire', 'Electricité': 'oui'
                }
            },
            {
                'matricule': '16', 'prenom': 'JAWAD', 'nom': 'MARZAK', 'equipe': 'V.M 31 à 34, 93 à 96', 'remarque': 'Jardinier',
                'competences': {
                    'Désherbage': 'débutant', 'Binage': 'débutant', 'Confection des cuvettes': 'débutant',
                    'Taille de nettoyage': 'débutant', 'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '20', 'prenom': 'ABD EL AZIZ', 'nom': 'SKENNDRI', 'equipe': 'V.M ESPACE COMMUN', 'remarque': 'chef d\'équipe',
                'competences': {
                    'Gestion d\'équipe': 'intermédiaire', 'Tondeuse': 'expert', 'Débroussailleuse': 'débutant',
                    'Tronçonneuse': 'intermédiaire', 'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'expert', 'Taille de décoration': 'expert', 'Arrosage': 'expert',
                    'Elagage de palmiers': 'expert', 'Nettoyage général': 'expert', 'Voiture': 'oui', 'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '25', 'prenom': 'EL FAJRI', 'nom': 'OTHMANE', 'equipe': 'V.M ESPACE COMMUN', 'remarque': 'Jardinier',
                'competences': {
                    'Gestion d\'équipe': 'intermédiaire', 'Tondeuse': 'expert', 'Débroussailleuse': 'débutant',
                    'Tronçonneuse': 'intermédiaire', 'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'expert', 'Taille de décoration': 'expert', 'Arrosage': 'expert',
                    'Elagage de palmiers': 'expert', 'Nettoyage général': 'expert', 'Voiture': 'oui', 'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '26', 'prenom': 'MOHAMED', 'nom': 'EL OUARRAQ', 'equipe': 'T.PARK', 'remarque': 'chef d\'équipe',
                'competences': {
                    'Gestion d\'équipe': 'intermédiaire', 'Tondeuse': 'débutant', 'Tronçonneuse': 'intermédiaire',
                    'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert', 'Taille de nettoyage': 'expert',
                    'Taille de décoration': 'expert', 'Arrosage': 'expert', 'Elagage de palmiers': 'expert',
                    'Nettoyage général': 'intermédiaire', 'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '29', 'prenom': 'MOHAMED', 'nom': 'AIT ALI', 'equipe': 'H.HILTON', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'intermédiaire', 'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire',
                    'Confection des cuvettes': 'intermédiaire', 'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire',
                    'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '31', 'prenom': 'RACHID', 'nom': 'BENHADDIA', 'equipe': 'S.G.DICE', 'remarque': 'chef d\'équipe',
                'competences': {
                    'Gestion d\'équipe': 'débutant', 'Tondeuse': 'débutant', 'Tronçonneuse': 'débutant',
                    'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire', 'Arrosage': 'expert',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '37', 'prenom': 'SAID', 'nom': 'SELLAFI', 'equipe': 'SUPPLEANT', 'remarque': 'Magasinier',
                'competences': {
                    'Gestion d\'équipe': 'débutant', 'Tondeuse': 'débutant', 'Désherbage': 'expert',
                    'Binage': 'expert', 'Confection des cuvettes': 'expert', 'Taille de nettoyage': 'intermédiaire',
                    'Taille de décoration': 'débutant', 'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire', 'Voiture': 'oui', 'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '38', 'prenom': 'ABDERRAHIM', 'nom': 'EL BAJI', 'equipe': 'V.CT2', 'remarque': 'chef d\'équipe',
                'competences': {
                    'Gestion d\'équipe': 'intermédiaire', 'Tondeuse': 'intermédiaire', 'Débroussailleuse': 'débutant',
                    'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire', 'Arrosage': 'intermédiaire',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '39', 'prenom': 'NABIL', 'nom': 'DRAOUI', 'equipe': 'V.M 26 à 30, 65 et 66', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire', 'Arrosage': 'intermédiaire',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '41', 'prenom': 'ABDERRAHIM', 'nom': 'EL MOUSSAOUI', 'equipe': 'T.PARK', 'remarque': 'Jardinier',
                'competences': {
                    'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire', 'Arrosage': 'intermédiaire',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '42', 'prenom': 'MILOUD', 'nom': 'LOUTFI', 'equipe': 'V.M 67 à 75', 'remarque': 'Jardinier',
                'competences': {
                    'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire', 'Arrosage': 'intermédiaire',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '43', 'prenom': 'LAHCEN', 'nom': 'RAHEL', 'equipe': 'CUB', 'remarque': 'chef d\'équipe',
                'competences': {
                    'Gestion d\'équipe': 'débutant', 'Tondeuse': 'débutant', 'Tronçonneuse': 'débutant',
                    'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire', 'Arrosage': 'expert',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire', 'Voiture': 'oui',
                    'Camion': 'oui', 'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '56', 'prenom': 'HAMID', 'nom': 'CHBIBI', 'equipe': 'V.CT2', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Tronçonneuse': 'débutant', 'Désherbage': 'intermédiaire',
                    'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire', 'Taille de nettoyage': 'intermédiaire',
                    'Taille de décoration': 'intermédiaire', 'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '75', 'prenom': 'ZOUHAIR', 'nom': 'NAJI', 'equipe': 'S.G.DICE', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire',
                    'Confection des cuvettes': 'intermédiaire', 'Taille de nettoyage': 'débutant', 'Taille de décoration': 'débutant',
                    'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire',
                    'Traitement phytosanitaire': 'oui'
                }
            },
            {
                'matricule': '76', 'prenom': 'ELHACHMI', 'nom': 'ELHENIOUI', 'equipe': 'T.PARK', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'intermédiaire', 'Débroussailleuse': 'intermédiaire', 'Tronçonneuse': 'débutant',
                    'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire',
                    'Taille de nettoyage': 'débutant', 'Taille de décoration': 'débutant', 'Arrosage': 'intermédiaire',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '77', 'prenom': 'MOHAMED', 'nom': 'AALAMI', 'equipe': 'V.CT2', 'remarque': 'Jardinier',
                'competences': {
                    'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire',
                    'Taille de nettoyage': 'débutant', 'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '78', 'prenom': 'SAID', 'nom': 'ENNAJI', 'equipe': 'E.M.PHENO', 'remarque': 'Jardinier',
                'competences': {
                    'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire',
                    'Taille de nettoyage': 'débutant', 'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '87', 'prenom': 'EL MOKHTAR', 'nom': 'EL QASSMY', 'equipe': 'R.LOCATIVES', 'remarque': 'Jardinier',
                'competences': {
                    'Tronçonneuse': 'débutant', 'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'débutant', 'Arrosage': 'intermédiaire', 'Elagage de palmiers': 'intermédiaire',
                    'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '89', 'prenom': 'SAID', 'nom': 'EL OUARRAQ', 'equipe': 'V.CT1', 'remarque': 'Jardinier',
                'competences': {
                    'Désherbage': 'débutant', 'Binage': 'débutant', 'Arrosage': 'débutant',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'débutant'
                }
            },
            {
                'matricule': '95', 'prenom': 'BOUJEMAA', 'nom': 'ELATTIFI', 'equipe': 'R.LOCATIVES', 'remarque': 'Caporal',
                'competences': {
                    'Tondeuse': 'intermédiaire', 'Débroussailleuse': 'intermédiaire', 'Tronçonneuse': 'intermédiaire',
                    'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'débutant', 'Arrosage': 'expert',
                    'Elagage de palmiers': 'expert', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '97', 'prenom': 'SAID', 'nom': 'EL ADRAOUI', 'equipe': 'H.HILTON', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Tronçonneuse': 'débutant', 'Désherbage': 'expert',
                    'Binage': 'expert', 'Confection des cuvettes': 'expert', 'Taille de nettoyage': 'débutant',
                    'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '98', 'prenom': 'YOUNES', 'nom': 'SDAIRI', 'equipe': 'V.M ESPACE COMMUN', 'remarque': 'Jardinier',
                'competences': {
                    'Désherbage': 'intermédiaire', 'Binage': 'intermédiaire', 'Confection des cuvettes': 'intermédiaire',
                    'Arrosage': 'débutant', 'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
            {
                'matricule': '104', 'prenom': 'MILOUD', 'nom': 'EL ARFAOUI', 'equipe': 'S.G.DICE', 'remarque': 'Jardinier',
                'competences': {
                    'Tondeuse': 'débutant', 'Débroussailleuse': 'débutant', 'Tronçonneuse': 'débutant',
                    'Désherbage': 'expert', 'Binage': 'expert', 'Confection des cuvettes': 'expert',
                    'Taille de nettoyage': 'intermédiaire', 'Taille de décoration': 'intermédiaire', 'Arrosage': 'intermédiaire',
                    'Elagage de palmiers': 'intermédiaire', 'Nettoyage général': 'intermédiaire'
                }
            },
        ]

        # Opérateurs sans compétences détaillées (matricules 134-190)
        operateurs_sans_competences = [
            ('134', 'YOUSSEF', 'ELGHAZOUANI', 'V.CT2', 'Jardinier'),
            ('135', 'ABDELOUHAB', 'DADSI', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('136', 'EL BACHIR', 'BELMAATI', 'CUB', 'Jardinier'),
            ('137', 'ABD EL KABIR', 'HAMDI', 'V.M TONTE', 'Jardinier'),
            ('138', 'SAID', 'MOUIDI', 'V.CT2', 'Jardinier'),
            ('139', 'MOHAMED', 'GARMOUL', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('140', 'MOURAD', 'LAABISSI', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('141', 'ISSAM', 'BOUCHRA', 'V.CT2', 'Jardinier'),
            ('142', 'ZIAD', 'BOUHAFA', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('143', 'AHMED', 'GHARIB', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('144', 'MOUSSA', 'EL YADINI', 'S.G.DICE', 'Jardinier'),
            ('146', 'NOUREDDINE', 'AMZAR', 'V.M 9 à 15, 49 à 52', 'Jardinier'),
            ('148', 'JAWAD', 'EL ABDOUNY', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('149', 'IMAD', 'BOUIHI', 'V.M 41 à 48', 'Jardinier'),
            ('150', 'MOUSSA', 'ENNAJI', 'V.M 21 à 25', 'Jardinier'),
            ('151', 'ABDELJALIL', 'MANDOUR', 'V.M 57 à 64', 'Jardinier'),
            ('152', 'HICHAM', 'BELQSSIR', 'V.M 84 à 92', 'Jardinier'),
            ('153', 'BDELJALIL', 'AIT EL HAMRI', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('154', 'MILOUD', 'BAKHAYUI', 'V.M 97 à 103', 'Jardinier'),
            ('155', 'MOHAMED', 'ECHTAIBI', 'CUB', 'Jardinier'),
            ('156', 'MOHAMED', 'KOULAL', 'V.M 1 à 8, 105 et 42', 'Jardinier'),
            ('157', 'MOHAMED', 'ELLOUAH', 'V.CT1', 'Jardinier'),
            ('158', 'ADIL', 'BOUICHIR', 'R.LOCATIVES', 'Jardinier'),
            ('160', 'ABDELMALEK', 'ETTAHIRI', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('161', 'MUSTAPHA', 'EL AARFAOUI', 'CUB', 'Jardinier'),
            ('162', 'ABDELHADI', 'BENALALA', 'V.M 35 à 40, 104 et 70', 'Jardinier'),
            ('163', 'ABDELFETTAH', 'DIDI', 'V.CT2', 'Jardinier'),
            ('164', 'ABDELLATIF', 'MAKKAOUI', 'V.M 16 à 20 et 53 à 56', 'Jardinier'),
            ('167', 'ABDERRAHIM', 'CABDI', 'CUB', 'Jardinier'),
            ('168', 'EL MUSTAPHA', 'ECHCHARKAOUY', 'V.M ESPACE COMMUN', 'Jardinier'),
            ('170', 'ABDELHAK', 'CHAIBATE', 'V.CT2', 'Jardinier'),
            ('174', 'BENATTAR', 'SEKRATI', 'T.PARK', 'Jardinier'),
            ('175', 'SAID', 'CHAFOUQ', 'T.PARK', 'Jardinier'),
            ('179', 'MOHAMED', 'BOUGHDIR', 'V.CT2', 'Jardinier'),
            ('182', 'AHMED', 'GHASSAN', 'V.M TONTE', 'Jardinier'),
            ('183', 'HASSAN', 'ZRAYDI', 'V.CT1', 'Jardinier'),
            ('184', 'SAID', 'HANIF', 'TECH ARROSAGE', 'TECH ARROSAGE'),
            ('186', 'YASSINE', 'HAIL', 'V.CT2', 'Jardinier'),
            ('187', 'ABDELHAMID', 'SGHURI', 'R.LOCATIVES', 'Jardinier'),
            ('188', 'ABDELKRIM', 'SOUFIANI', 'Hilton', 'Jardinier'),
            ('189', 'ESSOUGRATY', 'LEHMADY', 'T.PARK', 'Jardinier'),
            ('190', 'EL BACHIR', 'TAIR EL HAMAM', 'SUPPLEANT', 'Jardinier'),
        ]

        for mat, prenom, nom, equipe_nom, remarque in operateurs_sans_competences:
            operateurs_data.append({
                'matricule': mat,
                'prenom': prenom,
                'nom': nom,
                'equipe': equipe_nom,
                'remarque': remarque,
                'competences': {}
            })

        # Créer les opérateurs
        op_created = 0
        op_updated = 0
        comp_affectees = 0

        for data in operateurs_data:
            equipe = equipes_map.get(data['equipe'])
            email = f"{data['prenom'].lower().replace(' ', '')}.{data['nom'].lower().replace(' ', '')}@greensig.local"

            op, created = Operateur.objects.update_or_create(
                numero_immatriculation=data['matricule'],
                defaults={
                    'nom': data['nom'],
                    'prenom': data['prenom'],
                    'email': email,
                    'statut': StatutOperateur.ACTIF,
                    'equipe': equipe,
                    'date_embauche': date(2020, 1, 1),
                }
            )

            if created:
                op_created += 1
                self.stdout.write(self.style.SUCCESS(f'  Opérateur créé: {data["prenom"]} {data["nom"]} ({data["matricule"]})'))
            else:
                op_updated += 1
                self.stdout.write(f'  Opérateur MAJ: {data["prenom"]} {data["nom"]} ({data["matricule"]})')

            # Affecter compétences
            if data.get('competences'):
                CompetenceOperateur.objects.filter(operateur=op).delete()
                for nom_comp, niveau_str in data['competences'].items():
                    if nom_comp in competences_map:
                        niveau = self.normaliser_niveau(niveau_str)
                        if niveau != NiveauCompetence.NON:
                            CompetenceOperateur.objects.create(
                                operateur=op,
                                competence=competences_map[nom_comp],
                                niveau=niveau,
                                date_acquisition=date.today(),
                            )
                            comp_affectees += 1

        # ====================================================================
        # ÉTAPE 4: Affecter les chefs d'équipe
        # ====================================================================
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("ÉTAPE 4: Affectation des chefs d'équipe"))

        chefs_equipe = [
            ('2', 'V.CT1'),      # JILALI ESSADDIQI
            ('20', 'V.M ESPACE COMMUN'),  # ABD EL AZIZ SKENNDRI
            ('26', 'T.PARK'),    # MOHAMED EL OUARRAQ
            ('31', 'S.G.DICE'),  # RACHID BENHADDIA
            ('38', 'V.CT2'),     # ABDERRAHIM EL BAJI
            ('43', 'CUB'),       # LAHCEN RAHEL
        ]

        for matricule, equipe_nom in chefs_equipe:
            try:
                operateur = Operateur.objects.get(numero_immatriculation=matricule)
                equipe = Equipe.objects.get(nom_equipe=equipe_nom)
                equipe.chef_equipe = operateur
                equipe.save()
                self.stdout.write(self.style.SUCCESS(f'  Chef affecté: {operateur.prenom} {operateur.nom} → {equipe_nom}'))
            except (Operateur.DoesNotExist, Equipe.DoesNotExist) as e:
                self.stdout.write(self.style.WARNING(f'  Erreur: {e}'))

        # ====================================================================
        # RÉSUMÉ
        # ====================================================================
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("="*80))
        self.stdout.write(self.style.SUCCESS("IMPORTATION TERMINÉE"))
        self.stdout.write(self.style.SUCCESS("="*80))
        self.stdout.write(f"Compétences: {len(competences_map)}")
        self.stdout.write(f"Équipes: {len(equipes_map)}")
        self.stdout.write(f"Opérateurs créés: {op_created}")
        self.stdout.write(f"Opérateurs MAJ: {op_updated}")
        self.stdout.write(f"Total opérateurs: {op_created + op_updated}")
        self.stdout.write(f"Compétences affectées: {comp_affectees}")
        self.stdout.write(self.style.SUCCESS("="*80))
