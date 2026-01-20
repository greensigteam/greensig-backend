"""
Script pour vérifier les tâches liées aux réclamations.
Usage: python check_taches_reclamations.py
"""

import os
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')

import django
django.setup()

from api_planification.models import Tache
from api_reclamations.models import Reclamation
from django.db.models import Q


def main():
    print("=" * 60)
    print("VÉRIFICATION DES TÂCHES LIÉES AUX RÉCLAMATIONS")
    print("=" * 60)

    # Statistiques générales
    total_taches = Tache.objects.filter(deleted_at__isnull=True).count()
    total_reclamations = Reclamation.objects.count()

    print(f"\nTotal tâches (non supprimées): {total_taches}")
    print(f"Total réclamations: {total_reclamations}")

    # Tâches liées aux réclamations
    taches_avec_reclamation = Tache.objects.filter(
        deleted_at__isnull=True,
        reclamation__isnull=False
    )
    print(f"\nTâches liées à une réclamation: {taches_avec_reclamation.count()}")

    # Détail des tâches avec réclamation
    if taches_avec_reclamation.exists():
        print("\n--- DÉTAIL DES TÂCHES AVEC RÉCLAMATION ---")
        for t in taches_avec_reclamation.select_related(
            'reclamation', 'reclamation__site', 'id_type_tache', 'id_equipe', 'id_structure_client'
        )[:10]:
            print(f"\n  Tâche ID: {t.id}")
            print(f"    - Type: {t.id_type_tache.nom_tache if t.id_type_tache else 'N/A'}")
            print(f"    - Statut: {t.statut}")
            print(f"    - Réclamation: {t.reclamation.numero_reclamation}")
            print(f"    - Site réclamation: {t.reclamation.site.nom_site if t.reclamation.site else 'N/A'}")
            print(f"    - Équipe (id_equipe): {t.id_equipe.nom_equipe if t.id_equipe else 'N/A'}")
            print(f"    - Structure client: {t.id_structure_client.nom if t.id_structure_client else 'N/A'}")
            print(f"    - Nb objets liés: {t.objets.count()}")
            print(f"    - Nb équipes M2M: {t.equipes.count()}")

    # Vérifier les problèmes potentiels
    print("\n--- DIAGNOSTIC DES PROBLÈMES ---")

    # Tâches avec réclamation mais sans site sur la réclamation
    taches_sans_site = taches_avec_reclamation.filter(reclamation__site__isnull=True)
    print(f"Tâches avec réclamation SANS site: {taches_sans_site.count()}")

    # Tâches avec réclamation mais sans équipe
    taches_sans_equipe = taches_avec_reclamation.filter(
        id_equipe__isnull=True,
        equipes__isnull=True
    ).distinct()
    print(f"Tâches avec réclamation SANS équipe: {taches_sans_equipe.count()}")

    # Tâches avec réclamation mais sans structure_client
    taches_sans_structure = taches_avec_reclamation.filter(id_structure_client__isnull=True)
    print(f"Tâches avec réclamation SANS structure_client: {taches_sans_structure.count()}")

    # Tâches avec réclamation mais sans objets
    taches_sans_objets = taches_avec_reclamation.filter(objets__isnull=True)
    print(f"Tâches avec réclamation SANS objets: {taches_sans_objets.count()}")

    # Test du nouveau filtre pour SUPERVISEUR
    print("\n--- TEST DU FILTRE SUPERVISEUR ---")
    from api_users.models import Superviseur
    superviseurs = Superviseur.objects.all()[:3]

    for sup in superviseurs:
        # Ancien filtre (ne trouve que les tâches avec objets)
        ancien = Tache.objects.filter(
            deleted_at__isnull=True,
            objets__site__superviseur=sup
        ).distinct().count()

        # Nouveau filtre (inclut réclamations et équipes)
        nouveau = Tache.objects.filter(
            deleted_at__isnull=True
        ).filter(
            Q(objets__site__superviseur=sup) |
            Q(reclamation__site__superviseur=sup) |
            Q(id_equipe__site_principal__superviseur=sup) |
            Q(equipes__site_principal__superviseur=sup)
        ).distinct().count()

        print(f"  Superviseur {sup.utilisateur.email}:")
        print(f"    - Ancien filtre: {ancien} tâches")
        print(f"    - Nouveau filtre: {nouveau} tâches")
        print(f"    - Différence: +{nouveau - ancien} tâches")

    print("\n" + "=" * 60)
    print("FIN DE LA VÉRIFICATION")
    print("=" * 60)


if __name__ == '__main__':
    main()
