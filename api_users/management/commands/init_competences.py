# api_users/management/commands/init_competences.py
"""
Commande Django pour initialiser les competences et roles de base.

Usage:
    python manage.py init_competences
    python manage.py init_competences --force  # Reinitialise tout
"""
from django.core.management.base import BaseCommand
from api_users.models import Competence, Role, CategorieCompetence


class Command(BaseCommand):
    help = 'Initialise les competences et roles de base dans la base de donnees'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Reinitialise les donnees meme si elles existent deja',
        )

    def handle(self, *args, **options):
        force = options['force']

        self.stdout.write('Initialisation des donnees de base api_users...\n')

        # Initialiser les roles
        self.init_roles(force)

        # Initialiser les competences
        self.init_competences(force)

        self.stdout.write(self.style.SUCCESS('\nInitialisation terminee avec succes!'))

    def init_roles(self, force):
        """Initialise les roles de base."""
        self.stdout.write('  - Initialisation des roles...')

        roles = [
            {'nom_role': 'ADMIN', 'description': 'Administrateur systeme avec acces complet'},
            {'nom_role': 'CLIENT', 'description': 'Client (maitre d\'ouvrage) avec acces au portail client'},
            {'nom_role': 'CHEF_EQUIPE', 'description': 'Chef d\'equipe responsable d\'operateurs'},
            {'nom_role': 'OPERATEUR', 'description': 'Operateur terrain (jardinier)'},
        ]

        created_count = 0
        for role_data in roles:
            if force:
                role, created = Role.objects.update_or_create(
                    nom_role=role_data['nom_role'],
                    defaults={'description': role_data['description']}
                )
            else:
                role, created = Role.objects.get_or_create(
                    nom_role=role_data['nom_role'],
                    defaults={'description': role_data['description']}
                )
            if created:
                created_count += 1

        self.stdout.write(f'    {created_count} roles crees')

    def init_competences(self, force):
        """Initialise les competences de base selon le MCD."""
        self.stdout.write('  - Initialisation des competences...')

        # Competences techniques et operationnelles
        competences_techniques = [
            {
                'nom_competence': 'Utilisation de tondeuse',
                'description': 'Maitrise de l\'utilisation des tondeuses a gazon professionnelles',
                'ordre_affichage': 1
            },
            {
                'nom_competence': 'Utilisation de debroussailleuse',
                'description': 'Maitrise de l\'utilisation des debroussailleuses',
                'ordre_affichage': 2
            },
            {
                'nom_competence': 'Utilisation de tronconneuse',
                'description': 'Maitrise de l\'utilisation des tronconneuses avec habilitation',
                'ordre_affichage': 3
            },
            {
                'nom_competence': 'Desherbage manuel et mecanique',
                'description': 'Techniques de desherbage manuel et utilisation d\'outils mecaniques',
                'ordre_affichage': 4
            },
            {
                'nom_competence': 'Binage des sols',
                'description': 'Techniques de binage pour l\'aeration des sols',
                'ordre_affichage': 5
            },
            {
                'nom_competence': 'Confection des cuvettes',
                'description': 'Creation de cuvettes pour les plantations et l\'irrigation',
                'ordre_affichage': 6
            },
            {
                'nom_competence': 'Taille de nettoyage',
                'description': 'Taille d\'entretien et de nettoyage des vegetaux',
                'ordre_affichage': 7
            },
            {
                'nom_competence': 'Taille de decoration',
                'description': 'Taille ornementale et art topiaire',
                'ordre_affichage': 8
            },
            {
                'nom_competence': 'Arrosage',
                'description': 'Techniques d\'arrosage manuel et automatique des espaces verts',
                'ordre_affichage': 9
            },
            {
                'nom_competence': 'Elagage de palmiers',
                'description': 'Techniques specialisees d\'elagage de palmiers',
                'ordre_affichage': 10
            },
            {
                'nom_competence': 'Nettoyage general',
                'description': 'Nettoyage general des espaces verts et sites d\'intervention',
                'ordre_affichage': 11
            },
        ]

        # Competences organisationnelles et humaines
        competences_organisationnelles = [
            {
                'nom_competence': 'Gestion d\'equipe',
                'description': 'Capacite a diriger et coordonner une equipe d\'operateurs. '
                               'Prerequis pour etre chef d\'equipe.',
                'ordre_affichage': 1
            },
            {
                'nom_competence': 'Organisation des taches',
                'description': 'Organisation et repartition des taches au sein d\'une equipe',
                'ordre_affichage': 2
            },
            {
                'nom_competence': 'Supervision et coordination',
                'description': 'Supervision et coordination des interventions terrain',
                'ordre_affichage': 3
            },
            {
                'nom_competence': 'Respect des procedures',
                'description': 'Respect des consignes de securite et des procedures operationnelles',
                'ordre_affichage': 4
            },
        ]

        created_count = 0

        # Creer les competences techniques
        for comp_data in competences_techniques:
            if force:
                comp, created = Competence.objects.update_or_create(
                    nom_competence=comp_data['nom_competence'],
                    defaults={
                        'categorie': CategorieCompetence.TECHNIQUE,
                        'description': comp_data['description'],
                        'ordre_affichage': comp_data['ordre_affichage']
                    }
                )
            else:
                comp, created = Competence.objects.get_or_create(
                    nom_competence=comp_data['nom_competence'],
                    defaults={
                        'categorie': CategorieCompetence.TECHNIQUE,
                        'description': comp_data['description'],
                        'ordre_affichage': comp_data['ordre_affichage']
                    }
                )
            if created:
                created_count += 1

        # Creer les competences organisationnelles
        for comp_data in competences_organisationnelles:
            if force:
                comp, created = Competence.objects.update_or_create(
                    nom_competence=comp_data['nom_competence'],
                    defaults={
                        'categorie': CategorieCompetence.ORGANISATIONNELLE,
                        'description': comp_data['description'],
                        'ordre_affichage': comp_data['ordre_affichage']
                    }
                )
            else:
                comp, created = Competence.objects.get_or_create(
                    nom_competence=comp_data['nom_competence'],
                    defaults={
                        'categorie': CategorieCompetence.ORGANISATIONNELLE,
                        'description': comp_data['description'],
                        'ordre_affichage': comp_data['ordre_affichage']
                    }
                )
            if created:
                created_count += 1

        self.stdout.write(f'    {created_count} competences creees')
