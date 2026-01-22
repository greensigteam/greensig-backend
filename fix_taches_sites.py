#!/usr/bin/env python
"""
Script pour corriger les tâches existantes liées à des réclamations
qui n'ont pas de site/structure_client assigné.

Ce script:
1. Trouve toutes les tâches liées à une réclamation mais sans structure_client
2. Hérite du site de la réclamation
3. Met à jour la tâche avec la structure_client du site

Usage:
    cd backend
    python fix_taches_sites.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from api_planification.models import Tache
from api_reclamations.models import Reclamation


def show_status():
    """Affiche le statut actuel des tâches."""
    total_taches = Tache.objects.filter(deleted_at__isnull=True).count()
    taches_avec_reclamation = Tache.objects.filter(
        deleted_at__isnull=True,
        reclamation__isnull=False
    ).count()
    taches_avec_structure = Tache.objects.filter(
        deleted_at__isnull=True,
        id_structure_client__isnull=False
    ).count()
    taches_reclamation_sans_structure = Tache.objects.filter(
        deleted_at__isnull=True,
        reclamation__isnull=False,
        id_structure_client__isnull=True
    ).count()

    print(f"\n📊 STATUT DES TÂCHES:")
    print(f"   - Total tâches actives: {total_taches}")
    print(f"   - Avec réclamation: {taches_avec_reclamation}")
    print(f"   - Avec structure_client: {taches_avec_structure}")
    print(f"   - Liées à réclamation SANS structure_client: {taches_reclamation_sans_structure}")
    print()


def fix_taches_from_reclamations():
    """Corrige les tâches liées à des réclamations sans structure_client."""

    # Tâches liées à une réclamation mais sans structure_client
    taches_to_fix = Tache.objects.filter(
        deleted_at__isnull=True,
        reclamation__isnull=False,
        id_structure_client__isnull=True
    ).select_related('reclamation', 'reclamation__site', 'reclamation__site__structure_client')

    total = taches_to_fix.count()
    print(f"🔍 {total} tâche(s) à corriger (liées à réclamation, sans structure_client)")

    if total == 0:
        print("✅ Aucune tâche à corriger!")
        return

    fixed_count = 0
    no_site_count = 0
    no_structure_count = 0

    for tache in taches_to_fix:
        print(f"\n--- Tâche #{tache.id} (ref: {tache.reference}) ---")
        print(f"   Réclamation: {tache.reclamation.numero_reclamation}")

        # Vérifier si la réclamation a un site
        if not tache.reclamation.site:
            print(f"   ⚠️ La réclamation n'a pas de site")
            no_site_count += 1
            continue

        site = tache.reclamation.site
        print(f"   Site: {site.nom_site}")

        # Vérifier si le site a une structure_client
        if not site.structure_client:
            print(f"   ⚠️ Le site n'a pas de structure_client")
            no_structure_count += 1

            # Essayer avec le client legacy
            if hasattr(site, 'client') and site.client:
                tache.id_client = site.client
                tache.save(update_fields=['id_client'])
                print(f"   ✅ Client legacy assigné: {site.client}")
                fixed_count += 1
            continue

        # Assigner la structure_client
        tache.id_structure_client = site.structure_client

        # Aussi assigner le client legacy si disponible
        if hasattr(site, 'client') and site.client and not tache.id_client:
            tache.id_client = site.client

        tache.save(update_fields=['id_structure_client', 'id_client'])
        print(f"   ✅ Structure client assignée: {site.structure_client}")
        fixed_count += 1

    print(f"\n" + "="*50)
    print(f"📊 RÉSUMÉ:")
    print(f"   - Total tâches traitées: {total}")
    print(f"   - Corrigées: {fixed_count}")
    print(f"   - Réclamation sans site: {no_site_count}")
    print(f"   - Site sans structure_client: {no_structure_count}")
    print(f"="*50)


def fix_reclamations_sites_first():
    """Corrige d'abord les réclamations qui n'ont pas de site."""
    from api.models import Site, SousSite

    reclamations_to_fix = Reclamation.objects.filter(
        localisation__isnull=False,
        site__isnull=True
    )

    total = reclamations_to_fix.count()
    if total == 0:
        return 0

    print(f"\n🔧 Correction préalable: {total} réclamation(s) sans site...")

    fixed = 0
    for rec in reclamations_to_fix:
        # Essayer de trouver la zone d'abord
        found_zone = SousSite.objects.filter(
            geometrie__intersects=rec.localisation
        ).select_related('site').first()

        if found_zone:
            rec.zone = found_zone
            rec.site = found_zone.site
            rec.save(update_fields=['zone', 'site'])
            fixed += 1
            continue

        # Sinon chercher le site directement
        found_site = Site.objects.filter(
            geometrie_emprise__intersects=rec.localisation
        ).first()

        if found_site:
            rec.site = found_site
            rec.save(update_fields=['site'])
            fixed += 1

    print(f"   ✅ {fixed} réclamation(s) corrigée(s)")
    return fixed


if __name__ == '__main__':
    print("="*50)
    print("🔧 SCRIPT DE CORRECTION DES SITES DES TÂCHES")
    print("="*50)

    # Afficher le statut actuel
    show_status()

    # Demander confirmation
    response = input("Voulez-vous corriger les tâches? (o/n): ")
    if response.lower() not in ['o', 'oui', 'y', 'yes']:
        print("❌ Annulé.")
        sys.exit(0)

    # D'abord corriger les réclamations sans site
    fix_reclamations_sites_first()

    # Ensuite corriger les tâches
    fix_taches_from_reclamations()

    print("\n✅ Terminé!")
    show_status()
