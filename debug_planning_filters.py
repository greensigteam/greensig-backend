#!/usr/bin/env python
"""
Script de diagnostic pour le système de filtrage du planning.

Ce script vérifie:
1. Les clients existants
2. Les tâches et leur liaison avec les clients
3. Les objets liés aux tâches
4. Les sites liés aux objets
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import Client
from api_planification.models import Tache
from api.models import Site

def main():
    print("=" * 80)
    print("🔍 DIAGNOSTIC - Système de filtrage Planning")
    print("=" * 80)
    print()

    # 1. CLIENTS
    print("1️⃣  CLIENTS")
    print("-" * 80)
    clients = Client.objects.select_related('utilisateur').all()
    print(f"   Nombre total de clients: {clients.count()}")

    if clients.exists():
        print("\n   Liste des clients:")
        for i, client in enumerate(clients[:10], 1):
            print(f"   {i}. ID: {client.utilisateur.id} | {client.nom_structure}")
            print(f"      Email: {client.utilisateur.email}")
    else:
        print("   ⚠️  AUCUN CLIENT TROUVÉ !")
        print("   → Vous devez créer des clients dans la base de données")
        print("   → Commande: python seed_users.py")

    print()

    # 2. SITES
    print("2️⃣  SITES")
    print("-" * 80)
    sites = Site.objects.all()
    print(f"   Nombre total de sites: {sites.count()}")

    if sites.exists():
        print("\n   Liste des sites:")
        for i, site in enumerate(sites[:10], 1):
            print(f"   {i}. ID: {site.id} | {site.nom_site}")
            if site.client:
                print(f"      Client: {site.client.nom_structure}")
            else:
                print(f"      ⚠️  Pas de client assigné")
    else:
        print("   ⚠️  AUCUN SITE TROUVÉ !")
        print("   → Vous devez importer des sites")
        print("   → Commande: python import_geojson.py")

    print()

    # 3. TÂCHES
    print("3️⃣  TÂCHES")
    print("-" * 80)
    taches = Tache.objects.select_related(
        'id_client', 'id_client__utilisateur', 'id_type_tache'
    ).prefetch_related('objets').filter(deleted_at__isnull=True)

    print(f"   Nombre total de tâches: {taches.count()}")

    # Stats
    taches_avec_client = taches.filter(id_client__isnull=False).count()
    taches_sans_client = taches.filter(id_client__isnull=True).count()

    print(f"   Tâches AVEC client: {taches_avec_client}")
    print(f"   Tâches SANS client: {taches_sans_client}")

    if taches_sans_client > 0:
        print(f"\n   ⚠️  {taches_sans_client} tâches n'ont pas de client assigné !")
        print("   → Ces tâches ne seront pas filtrables par client")

    print()

    # 4. TÂCHES PAR CLIENT
    if clients.exists() and taches.exists():
        print("4️⃣  TÂCHES PAR CLIENT")
        print("-" * 80)

        for client in clients[:5]:
            client_taches = taches.filter(id_client=client)
            print(f"\n   Client: {client.nom_structure} (ID: {client.utilisateur.id})")
            print(f"   → Nombre de tâches: {client_taches.count()}")

            if client_taches.exists():
                # Vérifier les objets liés
                taches_avec_objets = 0
                sites_ids = set()

                for tache in client_taches:
                    objets = tache.objets.all()
                    if objets.exists():
                        taches_avec_objets += 1
                        for obj in objets:
                            if obj.site:
                                sites_ids.add(obj.site.id)

                print(f"   → Tâches avec objets: {taches_avec_objets}/{client_taches.count()}")
                print(f"   → Sites concernés: {len(sites_ids)} sites")

                if sites_ids:
                    sites_list = Site.objects.filter(id__in=sites_ids)
                    print(f"   → Liste des sites: {', '.join([s.nom_site for s in sites_list])}")
                else:
                    print(f"   ⚠️  AUCUN SITE lié aux tâches de ce client !")
                    print(f"   → Les tâches n'ont pas d'objets liés")
                    print(f"   → Vérifiez que les tâches sont créées avec des objets")
            else:
                print(f"   ℹ️  Aucune tâche pour ce client")

        print()

    # 5. DIAGNOSTIC DU PROBLÈME
    print("5️⃣  DIAGNOSTIC")
    print("-" * 80)

    problemes = []

    if not clients.exists():
        problemes.append("❌ Aucun client dans la base de données")

    if not sites.exists():
        problemes.append("❌ Aucun site dans la base de données")

    if not taches.exists():
        problemes.append("❌ Aucune tâche dans la base de données")

    if taches_sans_client > 0:
        problemes.append(f"⚠️  {taches_sans_client} tâches sans client assigné")

    if taches.exists():
        taches_sans_objets = 0
        for tache in taches:
            if not tache.objets.exists():
                taches_sans_objets += 1

        if taches_sans_objets > 0:
            problemes.append(f"⚠️  {taches_sans_objets}/{taches.count()} tâches sans objets liés")

    if problemes:
        print("\n   🔴 PROBLÈMES DÉTECTÉS:")
        for probleme in problemes:
            print(f"   {probleme}")
        print()
        print("   📝 SOLUTIONS:")
        print("   1. Créer des clients: python seed_users.py")
        print("   2. Importer des sites: python import_geojson.py")
        print("   3. Créer des tâches via l'interface Planning")
        print("   4. Assigner un client aux tâches existantes")
        print("   5. Lier des objets aux tâches lors de la création")
    else:
        print("\n   ✅ TOUT EST CORRECT !")
        print("   → Les données sont bien configurées")
        print("   → Le filtrage devrait fonctionner")

    print()
    print("=" * 80)


if __name__ == '__main__':
    main()
