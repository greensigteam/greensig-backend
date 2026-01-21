"""
Script pour vérifier les données des réclamations dans la base de données.
Usage: python check_reclamations_data.py
"""

import os
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')

import django
django.setup()

from api_reclamations.models import Reclamation
from api_users.models import Equipe
from api.models import SousSite


def main():
    print("=" * 60)
    print("VÉRIFICATION DES DONNÉES DES RÉCLAMATIONS")
    print("=" * 60)

    # Statistiques générales
    total = Reclamation.objects.count()
    print(f"\nTotal réclamations: {total}")

    if total == 0:
        print("Aucune réclamation dans la base de données.")
        return

    # Équipe affectée
    print("\n--- ÉQUIPE AFFECTÉE ---")
    avec_equipe = Reclamation.objects.filter(equipe_affectee__isnull=False).count()
    sans_equipe = Reclamation.objects.filter(equipe_affectee__isnull=True).count()
    print(f"Avec équipe assignée: {avec_equipe}")
    print(f"Sans équipe assignée: {sans_equipe}")

    if avec_equipe > 0:
        print("\nExemples avec équipe:")
        for r in Reclamation.objects.filter(equipe_affectee__isnull=False).select_related('equipe_affectee')[:5]:
            print(f"  - {r.numero_reclamation}: {r.equipe_affectee.nom_equipe}")

    # Zone (SousSite)
    print("\n--- ZONE (SOUS-SITE) ---")
    avec_zone = Reclamation.objects.filter(zone__isnull=False).count()
    sans_zone = Reclamation.objects.filter(zone__isnull=True).count()
    print(f"Avec zone: {avec_zone}")
    print(f"Sans zone: {sans_zone}")

    if avec_zone > 0:
        print("\nExemples avec zone:")
        for r in Reclamation.objects.filter(zone__isnull=False).select_related('zone')[:5]:
            print(f"  - {r.numero_reclamation}: {r.zone.nom}")

    # Dates
    print("\n--- DATES ---")
    avec_date_prise_en_compte = Reclamation.objects.filter(date_prise_en_compte__isnull=False).count()
    avec_date_debut_traitement = Reclamation.objects.filter(date_debut_traitement__isnull=False).count()
    avec_date_resolution = Reclamation.objects.filter(date_resolution__isnull=False).count()
    avec_date_cloture = Reclamation.objects.filter(date_cloture_reelle__isnull=False).count()

    print(f"Avec date_prise_en_compte: {avec_date_prise_en_compte}")
    print(f"Avec date_debut_traitement: {avec_date_debut_traitement}")
    print(f"Avec date_resolution: {avec_date_resolution}")
    print(f"Avec date_cloture_reelle: {avec_date_cloture}")

    # Statuts
    print("\n--- STATUTS ---")
    from django.db.models import Count
    statuts = Reclamation.objects.values('statut').annotate(count=Count('id')).order_by('-count')
    for s in statuts:
        print(f"  {s['statut']}: {s['count']}")

    # Vérification des équipes disponibles
    print("\n--- ÉQUIPES DISPONIBLES ---")
    equipes = Equipe.objects.filter(actif=True)
    print(f"Total équipes actives: {equipes.count()}")
    for e in equipes[:10]:
        print(f"  - ID {e.id}: {e.nom_equipe}")

    # Vérification des sous-sites disponibles
    print("\n--- SOUS-SITES (ZONES) DISPONIBLES ---")
    sous_sites = SousSite.objects.all()
    print(f"Total sous-sites: {sous_sites.count()}")
    for ss in sous_sites[:10]:
        print(f"  - ID {ss.id}: {ss.nom} (Site: {ss.site.nom_site})")

    print("\n" + "=" * 60)
    print("FIN DE LA VÉRIFICATION")
    print("=" * 60)


if __name__ == '__main__':
    main()
