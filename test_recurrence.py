"""
Script de test pour la récurrence des tâches multi-jours
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import Tache, DistributionCharge
from api_planification.utils import dupliquer_tache_avec_distributions, dupliquer_tache_recurrence_multiple
from datetime import date

def test_recurrence_multi_jours():
    """
    Test de récurrence pour une tâche multi-jours
    """
    print("\n" + "="*80)
    print("TEST DE RÉCURRENCE - TÂCHE MULTI-JOURS")
    print("="*80 + "\n")

    # Trouver une tâche multi-jours existante avec plusieurs distributions
    taches_multi_jours = Tache.objects.filter(
        deleted_at__isnull=True
    ).exclude(
        date_debut_planifiee=models.F('date_fin_planifiee')
    ).prefetch_related('distributions_charge').order_by('-id')[:5]

    if not taches_multi_jours.exists():
        print("[X] Aucune tache multi-jours trouvee dans la base de donnees")
        print("   Veuillez d'abord creer une tache multi-jours avec plusieurs distributions")
        return

    # Prendre la première tâche
    tache_source = taches_multi_jours.first()
    nb_distributions = tache_source.distributions_charge.count()

    print(f"[*] Tache source selectionnee:")
    print(f"   ID: {tache_source.id}")
    print(f"   Reference: {tache_source.reference}")
    print(f"   Dates: {tache_source.date_debut_planifiee} -> {tache_source.date_fin_planifiee}")
    print(f"   Nombre de distributions: {nb_distributions}")

    if nb_distributions == 0:
        print("   [!] Cette tache n'a pas de distributions!")
        return

    # Afficher les distributions
    print(f"\n   Distributions existantes:")
    for dist in tache_source.distributions_charge.all():
        print(f"      - {dist.date}: {dist.heure_debut} - {dist.heure_fin} ({dist.heures_planifiees}h)")

    # Test 1: Duplication avec décalage de 30 jours (MONTHLY)
    print(f"\n" + "-"*80)
    print("TEST 1: Duplication avec décalage de 30 jours")
    print("-"*80)

    try:
        nouvelles_taches = dupliquer_tache_avec_distributions(
            tache_id=tache_source.id,
            decalage_jours=30,
            nombre_occurrences=2,  # Créer seulement 2 pour le test
            conserver_equipes=True,
            conserver_objets=True
        )

        print(f"[OK] Succes! {len(nouvelles_taches)} tache(s) creee(s)")

        for idx, tache in enumerate(nouvelles_taches, 1):
            print(f"\n   Occurrence #{idx}:")
            print(f"      ID: {tache.id}")
            print(f"      Référence: {tache.reference}")
            print(f"      Dates: {tache.date_debut_planifiee} → {tache.date_fin_planifiee}")

            distributions = tache.distributions_charge.all()
            print(f"      Distributions ({distributions.count()}):")
            for dist in distributions:
                print(f"         - {dist.date}: {dist.heure_debut} - {dist.heure_fin} ({dist.heures_planifiees}h)")

    except Exception as e:
        print(f"[ERROR] Erreur lors de la duplication: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Duplication avec fréquence MONTHLY
    print(f"\n" + "-"*80)
    print("TEST 2: Duplication avec fréquence MONTHLY")
    print("-"*80)

    try:
        nouvelles_taches = dupliquer_tache_recurrence_multiple(
            tache_id=tache_source.id,
            frequence='MONTHLY',
            nombre_occurrences=2,  # Créer seulement 2 pour le test
            conserver_equipes=True,
            conserver_objets=True
        )

        print(f"[OK] Succes! {len(nouvelles_taches)} tache(s) creee(s)")

        for idx, tache in enumerate(nouvelles_taches, 1):
            print(f"\n   Occurrence #{idx}:")
            print(f"      ID: {tache.id}")
            print(f"      Référence: {tache.reference}")
            print(f"      Dates: {tache.date_debut_planifiee} → {tache.date_fin_planifiee}")

            distributions = tache.distributions_charge.all()
            print(f"      Distributions ({distributions.count()}):")
            for dist in distributions:
                print(f"         - {dist.date}: {dist.heure_debut} - {dist.heure_fin} ({dist.heures_planifiees}h)")

    except Exception as e:
        print(f"[ERROR] Erreur lors de la duplication: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("FIN DU TEST")
    print("="*80 + "\n")

if __name__ == '__main__':
    from django.db import models
    test_recurrence_multi_jours()
