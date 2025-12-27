#!/usr/bin/env python
"""
Script pour vérifier les doublons dans la base de données GreenSIG.
Identifie les sites ayant le même nom ou code.
"""
import os
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from django.db.models import Count
from api.models import Site

def check_duplicate_sites():
    """Vérifie les sites en doublon par nom ou code."""

    print("=" * 70)
    print("VÉRIFICATION DES DOUBLONS DANS LA BASE DE DONNÉES")
    print("=" * 70)

    # Vérifier les doublons par nom_site
    print("\n1. Sites avec le même nom_site:")
    print("-" * 70)

    duplicate_names = Site.objects.values('nom_site').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')

    if duplicate_names:
        for item in duplicate_names:
            nom = item['nom_site']
            count = item['count']
            print(f"  ❌ '{nom}' apparaît {count} fois")

            # Afficher les IDs
            sites = Site.objects.filter(nom_site=nom)
            ids = [str(s.id) for s in sites]
            print(f"     IDs: {', '.join(ids)}")
            print()
    else:
        print("  ✅ Aucun doublon trouvé par nom_site")

    # Vérifier les doublons par code_site
    print("\n2. Sites avec le même code_site:")
    print("-" * 70)

    duplicate_codes = Site.objects.exclude(code_site__isnull=True).exclude(code_site='').values('code_site').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')

    if duplicate_codes:
        for item in duplicate_codes:
            code = item['code_site']
            count = item['count']
            print(f"  ❌ Code '{code}' apparaît {count} fois")

            # Afficher les IDs
            sites = Site.objects.filter(code_site=code)
            ids = [str(s.id) for s in sites]
            print(f"     IDs: {', '.join(ids)}")
            print()
    else:
        print("  ✅ Aucun doublon trouvé par code_site")

    # Statistiques générales
    print("\n3. Statistiques générales:")
    print("-" * 70)
    total_sites = Site.objects.count()
    unique_names = Site.objects.values('nom_site').distinct().count()
    print(f"  Total de sites: {total_sites}")
    print(f"  Noms uniques: {unique_names}")

    if total_sites != unique_names:
        print(f"  ⚠️  Différence: {total_sites - unique_names} site(s) en doublon")
    else:
        print("  ✅ Tous les noms de sites sont uniques")

    print("\n" + "=" * 70)
    print("FIN DE LA VÉRIFICATION")
    print("=" * 70)

if __name__ == '__main__':
    check_duplicate_sites()
