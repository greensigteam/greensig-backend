#!/usr/bin/env python
"""Debug: Vérifie l'état des réclamations et leurs sites"""

import os
import sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from api_reclamations.models import Reclamation
from api_planification.models import Tache

print("="*60)
print("DIAGNOSTIC DES RÉCLAMATIONS ET TÂCHES")
print("="*60)

# 1. Réclamations
print("\n📋 RÉCLAMATIONS:")
reclamations = Reclamation.objects.all().select_related('site', 'site__structure_client')[:10]
for rec in reclamations:
    site_info = f"{rec.site.nom_site} (id={rec.site.id})" if rec.site else "❌ AUCUN"
    structure = rec.site.structure_client if rec.site and rec.site.structure_client else "❌ AUCUNE"
    localisation = "✅ Oui" if rec.localisation else "❌ Non"
    print(f"  - {rec.numero_reclamation}: site={site_info}, structure={structure}, localisation={localisation}")

# 2. Stats réclamations
total_rec = Reclamation.objects.count()
rec_avec_site = Reclamation.objects.filter(site__isnull=False).count()
rec_avec_loc = Reclamation.objects.filter(localisation__isnull=False).count()
rec_loc_sans_site = Reclamation.objects.filter(localisation__isnull=False, site__isnull=True).count()

print(f"\n📊 STATS RÉCLAMATIONS:")
print(f"  - Total: {total_rec}")
print(f"  - Avec site: {rec_avec_site}")
print(f"  - Avec localisation: {rec_avec_loc}")
print(f"  - Avec localisation SANS site: {rec_loc_sans_site}")

# 3. Tâches liées à des réclamations
print("\n📋 TÂCHES LIÉES À DES RÉCLAMATIONS:")
taches = Tache.objects.filter(
    deleted_at__isnull=True,
    reclamation__isnull=False
).select_related('reclamation', 'reclamation__site', 'id_structure_client')[:10]

for tache in taches:
    rec_site = tache.reclamation.site.nom_site if tache.reclamation and tache.reclamation.site else "❌ AUCUN"
    tache_structure = tache.id_structure_client if tache.id_structure_client else "❌ AUCUNE"
    print(f"  - Tâche #{tache.id}: réclamation={tache.reclamation.numero_reclamation}, "
          f"site_rec={rec_site}, structure_tache={tache_structure}")

# 4. Stats tâches
total_taches = Tache.objects.filter(deleted_at__isnull=True).count()
taches_avec_rec = Tache.objects.filter(deleted_at__isnull=True, reclamation__isnull=False).count()
taches_avec_structure = Tache.objects.filter(deleted_at__isnull=True, id_structure_client__isnull=False).count()
taches_rec_sans_structure = Tache.objects.filter(
    deleted_at__isnull=True,
    reclamation__isnull=False,
    id_structure_client__isnull=True
).count()

print(f"\n📊 STATS TÂCHES:")
print(f"  - Total actives: {total_taches}")
print(f"  - Avec réclamation: {taches_avec_rec}")
print(f"  - Avec structure_client: {taches_avec_structure}")
print(f"  - Avec réclamation SANS structure: {taches_rec_sans_structure}")

# 5. Vérifier si les sites ont des structure_client
print("\n📋 SITES ET LEURS STRUCTURES:")
from api.models import Site
sites = Site.objects.filter(actif=True).select_related('structure_client')[:10]
for site in sites:
    structure = site.structure_client if site.structure_client else "❌ AUCUNE"
    print(f"  - {site.nom_site} (id={site.id}): structure_client={structure}")

print("\n" + "="*60)
