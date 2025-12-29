#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Assigner une équipe au site d'un CLIENT pour test"""
import os
import sys
import django

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import Utilisateur, Client, Equipe
from api.models import Site

print("\n" + "="*70)
print("ASSIGNATION D'ÉQUIPES AUX SITES DU CLIENT")
print("="*70)

try:
    # Trouver le CLIENT
    client_user = Utilisateur.objects.filter(roles_utilisateur__role__nom_role='CLIENT').first()
    if not client_user or not hasattr(client_user, 'client_profile'):
        print('\n❌ Aucun CLIENT trouvé')
        exit(1)

    client = client_user.client_profile
    print(f'\n✅ CLIENT: {client_user.email}')

    # Sites du client
    client_sites = Site.objects.filter(client=client)
    print(f'\n📍 Sites du CLIENT ({client_sites.count()}) :')
    for site in client_sites:
        print(f'  - {site.nom_site} (ID: {site.id})')

    # Trouver des équipes sans site ou avec d'autres sites
    equipes_disponibles = Equipe.objects.filter(site__isnull=True)[:3]
    if not equipes_disponibles.exists():
        # Prendre des équipes existantes
        equipes_disponibles = Equipe.objects.all()[:3]

    print(f'\n👥 Équipes disponibles ({equipes_disponibles.count()}) :')
    for equipe in equipes_disponibles:
        site_nom = equipe.site.nom_site if equipe.site else "AUCUN"
        print(f'  - {equipe.nom_equipe} (Site actuel: {site_nom})')

    # Assigner les équipes aux sites du client
    if client_sites.exists() and equipes_disponibles.exists():
        print(f'\n🔧 Assignation des équipes aux sites du client...')
        for i, equipe in enumerate(equipes_disponibles):
            # Assigner à un site du client (rotation)
            site = client_sites[i % client_sites.count()]
            ancien_site = equipe.site.nom_site if equipe.site else "AUCUN"
            equipe.site = site
            equipe.save()
            print(f'  ✅ {equipe.nom_equipe}: {ancien_site} → {site.nom_site}')

        # Vérification
        equipes_client = Equipe.objects.filter(site__client=client)
        print(f'\n✅ SUCCÈS ! Le CLIENT peut maintenant voir {equipes_client.count()} équipes:')
        for equipe in equipes_client:
            nb_membres = equipe.operateurs.count()
            print(f'  - {equipe.nom_equipe} | Site: {equipe.site.nom_site} | Membres: {nb_membres}')
    else:
        print('\n❌ Pas assez de données pour l\'assignation')

except Exception as e:
    print(f'\n❌ ERREUR: {e}')
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("FIN DE L'ASSIGNATION")
print("="*70 + "\n")
