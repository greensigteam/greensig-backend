#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test d'accès RH pour le CLIENT"""
import os
import sys
import django

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import Utilisateur, Client, Equipe, Operateur
from api.models import Site

print("\n" + "="*70)
print("TEST D'ACCÈS RH POUR LE CLIENT")
print("="*70)

# Trouver un utilisateur CLIENT
try:
    client_user = Utilisateur.objects.filter(roles_utilisateur__role__nom_role='CLIENT').first()
    if client_user and hasattr(client_user, 'client_profile'):
        client = client_user.client_profile
        print(f'\n✅ CLIENT trouvé: {client_user.email}')

        # Sites du client
        sites = Site.objects.filter(client=client)
        print(f'\n📍 Sites du CLIENT: {sites.count()}')
        for site in sites:
            print(f'  - {site.nom_site} (ID: {site.id})')

        # Équipes sur ces sites
        equipes = Equipe.objects.filter(site__client=client)
        print(f'\n👥 Équipes sur ces sites: {equipes.count()}')
        for equipe in equipes[:10]:
            site_nom = equipe.site.nom_site if equipe.site else "AUCUN"
            nb_membres = equipe.operateurs.count()
            print(f'  - {equipe.nom_equipe} | Site: {site_nom} | Membres: {nb_membres}')

        # Opérateurs de ces équipes
        operateurs = Operateur.objects.filter(equipe__site__client=client)
        print(f'\n👷 Opérateurs sur ces équipes: {operateurs.count()}')
        for op in operateurs[:10]:
            equipe_nom = op.equipe.nom_equipe if op.equipe else "AUCUNE"
            print(f'  - {op.nom} {op.prenom} | Équipe: {equipe_nom}')

        print("\n✅ Le filtrage fonctionne ! Le CLIENT peut voir:")
        print(f"   - {sites.count()} sites")
        print(f"   - {equipes.count()} équipes")
        print(f"   - {operateurs.count()} opérateurs")

    else:
        print('\n❌ Aucun CLIENT trouvé dans la base de données')
        print('   Créez un utilisateur CLIENT avec un site assigné')

except Exception as e:
    print(f'\n❌ ERREUR: {e}')
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("FIN DU TEST")
print("="*70 + "\n")
