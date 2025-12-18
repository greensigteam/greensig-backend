#!/usr/bin/env python
"""
Script pour attribuer automatiquement le rôle CLIENT à tous les utilisateurs
qui ont un profil Client mais n'ont pas encore le rôle CLIENT.
"""
import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import Client, Role, UtilisateurRole

def fix_client_roles():
    """Attribue le rôle CLIENT à tous les clients qui ne l'ont pas."""
    # Récupérer ou créer le rôle CLIENT
    role_client, created = Role.objects.get_or_create(
        nom_role='CLIENT',
        defaults={'description': 'Utilisateur client'}
    )
    
    if created:
        print(f"✓ Rôle CLIENT créé")
    
    # Récupérer tous les clients
    clients = Client.objects.all()
    print(f"\nNombre total de clients: {clients.count()}")
    
    fixed_count = 0
    for client in clients:
        # Vérifier si l'utilisateur a déjà le rôle CLIENT
        has_role = UtilisateurRole.objects.filter(
            utilisateur=client.utilisateur,
            role=role_client
        ).exists()
        
        if not has_role:
            # Attribuer le rôle
            UtilisateurRole.objects.create(
                utilisateur=client.utilisateur,
                role=role_client
            )
            print(f"✓ Rôle CLIENT attribué à: {client.utilisateur.get_full_name()} ({client.utilisateur.email})")
            fixed_count += 1
        else:
            print(f"  Rôle déjà attribué: {client.utilisateur.get_full_name()}")
    
    print(f"\n{'='*60}")
    print(f"Résumé:")
    print(f"  - Clients traités: {clients.count()}")
    print(f"  - Rôles attribués: {fixed_count}")
    print(f"{'='*60}")

if __name__ == '__main__':
    print("Correction des rôles CLIENT...")
    print("="*60)
    fix_client_roles()
    print("\nTerminé!")
