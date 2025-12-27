import os
import sys
import django
from datetime import date

# Configuration de l'environnement Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import (
    Utilisateur, Role, UtilisateurRole, Client, Operateur, 
    StatutOperateur, Competence, CompetenceOperateur, NiveauCompetence
)

DEFAULT_PASSWORD = "admin123"

def create_role_if_not_exists(nom, description):
    role, created = Role.objects.get_or_create(nom_role=nom, defaults={'description': description})
    if created:
        print(f"Role {nom} cree.")
    return role

def seed_users():
    print("\n🚀 Debut du peuplement des utilisateurs...")

    # 1. S'assurer que les roles existent
    roles = {
        'ADMIN': create_role_if_not_exists('ADMIN', 'Administrateur'),
        'CLIENT': create_role_if_not_exists('CLIENT', 'Client'),
        'CHEF_EQUIPE': create_role_if_not_exists('CHEF_EQUIPE', 'Chef d\'equipe'),
        'OPERATEUR': create_role_if_not_exists('OPERATEUR', 'Operateur terrain'),
    }

    # 2. Creer 6 Clients
    print("\n🏢 Creation de 6 Clients...")
    for i in range(1, 7):
        email = f"client{i}@example.com"
        user, created = Utilisateur.objects.get_or_create(
            email=email,
            defaults={
                'nom': f'CLIENT_{i}',
                'prenom': f'Structure_{i}',
                'actif': True
            }
        )
        user.set_password(DEFAULT_PASSWORD)
        user.save()
        
        UtilisateurRole.objects.get_or_create(utilisateur=user, role=roles['CLIENT'])
        
        client, c_created = Client.objects.get_or_create(
            utilisateur=user,
            defaults={
                'nom_structure': f'Entreprise Green {i}',
                'adresse': f'{i} Zone Industrielle, Benguerir',
                'telephone': f'+212 524 000 00{i}',
                'contact_principal': f'Responsable {i}',
                'email_facturation': f'compta{i}@entreprise{i}.ma'
            }
        )
        if c_created:
            print(f"   ✅ Client {i} cree: {email}")

    # 3. Creer 3 Chefs d'equipe (sont aussi des operateurs)
    print("\n👨‍💼 Creation de 3 Chefs d'equipe...")
    # Pour que le chef soit valide dans les modeles, il lui faut la competence "Gestion d'équipe"
    # On la cree ici rapidement si elle n'existe pas
    comp_gestion, _ = Competence.objects.get_or_create(
        nom_competence="Gestion d'équipe",
        defaults={'categorie': 'ORGANISATIONNELLE'}
    )

    for i in range(1, 4):
        email = f"chef{i}@greensig.ma"
        user, created = Utilisateur.objects.get_or_create(
            email=email,
            defaults={
                'nom': f'CHEF',
                'prenom': f'Numero_{i}',
                'actif': True
            }
        )
        user.set_password(DEFAULT_PASSWORD)
        user.save()
        
        UtilisateurRole.objects.get_or_create(utilisateur=user, role=roles['OPERATEUR'])
        UtilisateurRole.objects.get_or_create(utilisateur=user, role=roles['CHEF_EQUIPE'])
        
        op, op_created = Operateur.objects.get_or_create(
            utilisateur=user,
            defaults={
                'numero_immatriculation': f'CHEF-2025-{i:03d}',
                'statut': StatutOperateur.ACTIF,
                'date_embauche': date(2023, 1, 1),
                'telephone': f'+212 600 000 00{i}'
            }
        )
        
        # Attribution de la competence de gestion (obligatoire pour etre chef d'equipe dans ce systeme)
        CompetenceOperateur.objects.get_or_create(
            operateur=op,
            competence=comp_gestion,
            defaults={'niveau': NiveauCompetence.EXPERT, 'date_acquisition': date(2023, 1, 1)}
        )

        if op_created:
            print(f"   ✅ Chef d'equipe {i} cree: {email}")

    # 4. Creer 10 Operateurs
    print("\n👷 Creation de 10 Operateurs...")
    for i in range(1, 11):
        email = f"operateur{i}@greensig.ma"
        user, created = Utilisateur.objects.get_or_create(
            email=email,
            defaults={
                'nom': f'OPERATEUR',
                'prenom': f'Numero_{i}',
                'actif': True
            }
        )
        user.set_password(DEFAULT_PASSWORD)
        user.save()
        
        UtilisateurRole.objects.get_or_create(utilisateur=user, role=roles['OPERATEUR'])
        
        op, op_created = Operateur.objects.get_or_create(
            utilisateur=user,
            defaults={
                'numero_immatriculation': f'OP-2025-{i:03d}',
                'statut': StatutOperateur.ACTIF,
                'date_embauche': date(2024, (i % 12) or 1, 1),
                'telephone': f'+212 611 000 0{i:02d}'
            }
        )
        if op_created:
            print(f"   ✅ Operateur {i} cree: {email}")

if __name__ == "__main__":
    seed_users()
    print("\n✨ Peuplement des utilisateurs termine!")
