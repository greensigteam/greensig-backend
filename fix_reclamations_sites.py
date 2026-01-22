#!/usr/bin/env python
"""
Script pour corriger les réclamations existantes qui n'ont pas de site assigné.

Ce script:
1. Parcourt toutes les réclamations avec une localisation mais sans site
2. Détecte automatiquement le site en utilisant la géométrie
3. Met à jour la réclamation avec le site détecté

Usage:
    cd backend
    python fix_reclamations_sites.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from api_reclamations.models import Reclamation
from api.models import Site, SousSite


def fix_reclamations_without_site():
    """Corrige les réclamations qui ont une localisation mais pas de site."""

    # Récupérer les réclamations avec localisation mais sans site
    reclamations_to_fix = Reclamation.objects.filter(
        localisation__isnull=False,
        site__isnull=True
    )

    total = reclamations_to_fix.count()
    print(f"🔍 {total} réclamation(s) à corriger (avec localisation mais sans site)")

    if total == 0:
        print("✅ Aucune réclamation à corriger!")
        return

    fixed_count = 0
    zone_detected_count = 0
    no_site_found_count = 0

    for reclamation in reclamations_to_fix:
        print(f"\n--- Réclamation {reclamation.numero_reclamation} ---")
        print(f"   Localisation type: {reclamation.localisation.geom_type}")

        # Essayer de trouver la zone (SousSite) d'abord
        found_zone = SousSite.objects.filter(
            geometrie__intersects=reclamation.localisation
        ).select_related('site').first()

        if found_zone:
            reclamation.zone = found_zone
            reclamation.site = found_zone.site
            reclamation.save(update_fields=['zone', 'site'])
            print(f"   ✅ Zone détectée: {found_zone.nom} (Site: {found_zone.site.nom_site})")
            fixed_count += 1
            zone_detected_count += 1
            continue

        # Si pas de zone, chercher le site directement
        found_site = Site.objects.filter(
            geometrie_emprise__intersects=reclamation.localisation
        ).first()

        if found_site:
            reclamation.site = found_site
            reclamation.save(update_fields=['site'])
            print(f"   ✅ Site détecté: {found_site.nom_site}")
            fixed_count += 1
            continue

        # Aucun site trouvé
        print(f"   ⚠️ Aucun site trouvé pour cette localisation")
        no_site_found_count += 1

    print(f"\n" + "="*50)
    print(f"📊 RÉSUMÉ:")
    print(f"   - Total réclamations traitées: {total}")
    print(f"   - Corrigées avec zone + site: {zone_detected_count}")
    print(f"   - Corrigées avec site seul: {fixed_count - zone_detected_count}")
    print(f"   - Sans site trouvé: {no_site_found_count}")
    print(f"="*50)


def show_reclamations_status():
    """Affiche le statut actuel des réclamations par rapport aux sites."""

    total = Reclamation.objects.count()
    with_site = Reclamation.objects.filter(site__isnull=False).count()
    with_localisation = Reclamation.objects.filter(localisation__isnull=False).count()
    with_localisation_no_site = Reclamation.objects.filter(
        localisation__isnull=False,
        site__isnull=True
    ).count()

    print(f"\n📊 STATUT DES RÉCLAMATIONS:")
    print(f"   - Total: {total}")
    print(f"   - Avec site: {with_site} ({with_site/total*100:.1f}%)" if total > 0 else "   - Avec site: 0")
    print(f"   - Avec localisation: {with_localisation}")
    print(f"   - Avec localisation SANS site: {with_localisation_no_site}")
    print()


if __name__ == '__main__':
    print("="*50)
    print("🔧 SCRIPT DE CORRECTION DES SITES DES RÉCLAMATIONS")
    print("="*50)

    # Afficher le statut actuel
    show_reclamations_status()

    # Demander confirmation
    response = input("Voulez-vous corriger les réclamations sans site? (o/n): ")
    if response.lower() in ['o', 'oui', 'y', 'yes']:
        fix_reclamations_without_site()
        print("\n✅ Terminé!")
        show_reclamations_status()
    else:
        print("❌ Annulé.")
