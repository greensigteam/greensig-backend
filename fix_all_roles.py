#!/usr/bin/env python
"""
Script pour attribuer automatiquement les rôles appropriés à tous les utilisateurs
qui ont des profils spécifiques mais n'ont pas encore les rôles correspondants.
"""
import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import Client, Operateur, Role, UtilisateurRole

def fix_all_roles():
    """Attribue les rôles appropriés à tous les utilisateurs."""
    
    # ========================================================================
    # 1. CLIENTS
    # ========================================================================
    print("\n" + "="*60)
    print("CORRECTION DES RÔLES CLIENT")
    print("="*60)
    
    role_client, created = Role.objects.get_or_create(
        nom_role='CLIENT',
        defaults={'description': 'Utilisateur client'}
    )
    if created:
        print("✓ Rôle CLIENT créé")
    
    clients = Client.objects.all()
    print(f"Nombre total de clients: {clients.count()}")
    
    client_fixed = 0
    for client in clients:
        has_role = UtilisateurRole.objects.filter(
            utilisateur=client.utilisateur,
            role=role_client
        ).exists()
        
        if not has_role:
            UtilisateurRole.objects.create(
                utilisateur=client.utilisateur,
                role=role_client
            )
            print(f"✓ Rôle CLIENT attribué à: {client.utilisateur.get_full_name()} ({client.utilisateur.email})")
            client_fixed += 1
        else:
            print(f"  Rôle déjà attribué: {client.utilisateur.get_full_name()}")
    
    # ========================================================================
    # 2. OPÉRATEURS
    # ========================================================================
    print("\n" + "="*60)
    print("CORRECTION DES RÔLES OPÉRATEUR")
    print("="*60)
    
    role_operateur, created = Role.objects.get_or_create(
        nom_role='OPERATEUR',
        defaults={'description': 'Opérateur de terrain'}
    )
    if created:
        print("✓ Rôle OPERATEUR créé")
    
    operateurs = Operateur.objects.all()
    print(f"Nombre total d'opérateurs: {operateurs.count()}")
    
    operateur_fixed = 0
    for operateur in operateurs:
        has_role = UtilisateurRole.objects.filter(
            utilisateur=operateur.utilisateur,
            role=role_operateur
        ).exists()
        
        if not has_role:
            UtilisateurRole.objects.create(
                utilisateur=operateur.utilisateur,
                role=role_operateur
            )
            print(f"✓ Rôle OPERATEUR attribué à: {operateur.utilisateur.get_full_name()} ({operateur.utilisateur.email})")
            operateur_fixed += 1
        else:
            print(f"  Rôle déjà attribué: {operateur.utilisateur.get_full_name()}")
    
    # ========================================================================
    # 3. CHEFS D'ÉQUIPE
    # ========================================================================
    print("\n" + "="*60)
    print("CORRECTION DES RÔLES CHEF D'ÉQUIPE")
    print("="*60)
    
    role_chef, created = Role.objects.get_or_create(
        nom_role='CHEF_EQUIPE',
        defaults={'description': "Chef d'équipe"}
    )
    if created:
        print("✓ Rôle CHEF_EQUIPE créé")
    
    # Trouver tous les opérateurs qui sont chefs d'équipe
    from api_users.models import Equipe
    chefs = Operateur.objects.filter(equipes_dirigees__actif=True).distinct()
    print(f"Nombre total de chefs d'équipe: {chefs.count()}")
    
    chef_fixed = 0
    for chef in chefs:
        has_role = UtilisateurRole.objects.filter(
            utilisateur=chef.utilisateur,
            role=role_chef
        ).exists()
        
        if not has_role:
            UtilisateurRole.objects.create(
                utilisateur=chef.utilisateur,
                role=role_chef
            )
            equipes = chef.equipes_dirigees.filter(actif=True)
            equipes_noms = ", ".join([e.nom_equipe for e in equipes])
            print(f"✓ Rôle CHEF_EQUIPE attribué à: {chef.utilisateur.get_full_name()} ({equipes_noms})")
            chef_fixed += 1
        else:
            print(f"  Rôle déjà attribué: {chef.utilisateur.get_full_name()}")
    
    # ========================================================================
    # RÉSUMÉ
    # ========================================================================
    print("\n" + "="*60)
    print("RÉSUMÉ FINAL")
    print("="*60)
    print(f"Clients traités: {clients.count()} | Rôles attribués: {client_fixed}")
    print(f"Opérateurs traités: {operateurs.count()} | Rôles attribués: {operateur_fixed}")
    print(f"Chefs d'équipe traités: {chefs.count()} | Rôles attribués: {chef_fixed}")
    print(f"\nTotal de rôles attribués: {client_fixed + operateur_fixed + chef_fixed}")
    print("="*60)

if __name__ == '__main__':
    print("Correction de tous les rôles utilisateurs...")
    fix_all_roles()
    print("\n✅ Terminé!")
