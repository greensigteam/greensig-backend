#!/usr/bin/env python
"""
Script de diagnostic V2 - Relation indirecte Tâche → Objets → Site → Client
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import Client
from api_planification.models import Tache
from api.models import Site, Objet

def main():
    print("=" * 80)
    print("🔍 DIAGNOSTIC V2 - Relation indirecte")
    print("=" * 80)
    print()

    # Vérifier la structure
    print("📊 STRUCTURE DES RELATIONS")
    print("-" * 80)
    print("   Tâche → Objets (many-to-many)")
    print("   Objet → Site (ForeignKey)")
    print("   Site → Client (ForeignKey)")
    print()

    # 1. Vérifier les tâches avec objets
    taches = Tache.objects.prefetch_related('objets', 'objets__site', 'objets__site__client').filter(deleted_at__isnull=True)

    print("1️⃣  TÂCHES ET LEURS OBJETS")
    print("-" * 80)
    print(f"   Nombre total de tâches: {taches.count()}")

    taches_avec_objets = 0
    taches_sans_objets = 0

    for tache in taches:
        if tache.objets.exists():
            taches_avec_objets += 1
        else:
            taches_sans_objets += 1

    print(f"   Tâches AVEC objets: {taches_avec_objets}")
    print(f"   Tâches SANS objets: {taches_sans_objets}")
    print()

    # 2. Tâches par client (via relation indirecte)
    print("2️⃣  CLIENTS TROUVÉS VIA OBJETS")
    print("-" * 80)

    clients_map = {}  # {client_id: {'client': obj, 'taches': [], 'sites': set()}}

    for tache in taches:
        objets = tache.objets.select_related('site', 'site__client').all()

        for obj in objets:
            if obj.site and obj.site.client:
                client = obj.site.client
                client_id = client.utilisateur_id

                if client_id not in clients_map:
                    clients_map[client_id] = {
                        'client': client,
                        'taches': [],
                        'sites': set()
                    }

                if tache.id not in [t.id for t in clients_map[client_id]['taches']]:
                    clients_map[client_id]['taches'].append(tache)

                clients_map[client_id]['sites'].add(obj.site.id)

    print(f"   Nombre de clients avec des tâches: {len(clients_map)}")
    print()

    if clients_map:
        print("   Détails par client:")
        for client_id, data in clients_map.items():
            client = data['client']
            taches_count = len(data['taches'])
            sites_count = len(data['sites'])

            print(f"\n   📍 Client: {client.nom_structure} (ID: {client_id})")
            print(f"      → {taches_count} tâche(s)")
            print(f"      → {sites_count} site(s) concerné(s)")

            # Afficher les sites
            sites = Site.objects.filter(id__in=data['sites'])
            print(f"      → Sites: {', '.join([s.nom_site for s in sites])}")
    else:
        print("   ⚠️  Aucun client trouvé via les objets des tâches !")
        print("   → Les tâches ont des objets, mais les sites n'ont pas de client")
        print("   → Ou les objets n'ont pas de site")

    print()

    # 3. Diagnostic détaillé
    print("3️⃣  ANALYSE DÉTAILLÉE")
    print("-" * 80)

    # Tâches avec objets mais sans site
    taches_objets_sans_site = 0
    # Tâches avec objets et sites mais sans client
    taches_sites_sans_client = 0
    # Tâches complètes (objets → site → client)
    taches_completes = 0

    for tache in taches:
        objets = tache.objets.select_related('site', 'site__client').all()

        if not objets.exists():
            continue

        has_site = False
        has_client = False

        for obj in objets:
            if obj.site:
                has_site = True
                if obj.site.client:
                    has_client = True
                    break

        if not has_site:
            taches_objets_sans_site += 1
        elif not has_client:
            taches_sites_sans_client += 1
        else:
            taches_completes += 1

    print(f"   Tâches avec objets SANS site: {taches_objets_sans_site}")
    print(f"   Tâches avec sites SANS client: {taches_sites_sans_client}")
    print(f"   Tâches COMPLÈTES (objet→site→client): {taches_completes}")
    print()

    # 4. Solution proposée
    print("4️⃣  SOLUTION")
    print("-" * 80)

    if taches_completes > 0:
        print("   ✅ Vos tâches ont la chaîne complète Tâche→Objet→Site→Client")
        print()
        print("   📝 DEUX OPTIONS:")
        print()
        print("   Option A - Peupler id_client automatiquement (RECOMMANDÉ)")
        print("   ────────────────────────────────────────────────────────")
        print("   Cette option va remplir le champ 'id_client' de chaque tâche")
        print("   en se basant sur le client du site des objets.")
        print()
        print("   Voulez-vous exécuter cette mise à jour? (o/n): ", end='')

        # Pour l'instant, on affiche juste le script
        print("\n\n   Script à exécuter:")
        print("   " + "─" * 70)
        print("""
   from api_planification.models import Tache

   updated = 0
   for tache in Tache.objects.prefetch_related('objets__site__client').filter(deleted_at__isnull=True):
       if tache.id_client is None:  # Seulement si pas déjà assigné
           objets = tache.objets.select_related('site__client').all()
           for obj in objets:
               if obj.site and obj.site.client:
                   tache.id_client = obj.site.client
                   tache.save(update_fields=['id_client'])
                   updated += 1
                   break  # Prendre le premier client trouvé

   print(f"✅ {updated} tâches mises à jour")
        """)
        print()
        print("   Option B - Modifier le filtrage frontend")
        print("   ────────────────────────────────────────────")
        print("   Modifier la logique de filtrage pour utiliser")
        print("   la relation indirecte Tâche→Objet→Site→Client")

    elif taches_sites_sans_client > 0:
        print("   ⚠️  Les sites n'ont pas de client assigné")
        print()
        print("   Solution: Assigner les sites à leurs clients")
        print("   Django Admin > API > Sites > Sélectionner le client")

    elif taches_objets_sans_site > 0:
        print("   ⚠️  Les objets n'ont pas de site assigné")
        print()
        print("   Solution: Vérifier l'intégrité des données objets")

    else:
        print("   ⚠️  Les tâches n'ont pas d'objets liés")
        print()
        print("   Solution: Lors de la création des tâches,")
        print("   sélectionner au moins 1 objet inventaire")

    print()
    print("=" * 80)


if __name__ == '__main__':
    main()
