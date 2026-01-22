"""
Script de test pour la fonctionnalité temps_travail_total (Option 2: Approche Hybride)

Ce script teste les différentes sources de calcul du temps de travail :
1. Temps manuel (priorité absolue)
2. Heures réelles des distributions
3. Heures travaillées des participations
4. Charge estimée
5. Heures planifiées
6. Aucune donnée (0h)
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import Tache, DistributionCharge, ParticipationTache
from api_users.models import Utilisateur
from datetime import date, time
from django.db.models import Sum


def print_separator():
    print("\n" + "=" * 80 + "\n")


def print_temps_travail(tache, label=""):
    """Affiche le temps de travail total d'une tâche avec toutes les métadonnées."""
    temps = tache.temps_travail_total

    print(f"\n{'-' * 80}")
    if label:
        print(f"[*] {label}")
    print(f"{'-' * 80}")
    print(f"[ID] Tache ID: {tache.id}")
    print(f"[STATUS] Statut: {tache.statut}")
    print(f"")
    print(f"[TIME] Temps de travail total: {temps['heures']:.2f}h")
    print(f"[SOURCE] Source: {temps['source']}")
    print(f"[OK] Fiable: {'Oui' if temps['fiable'] else 'Non (estimation)'}")
    print(f"[EDIT] Manuel: {'Oui' if temps['manuel'] else 'Non (automatique)'}")

    if temps['manuel']:
        print(f"[USER] Saisi par: {temps['manuel_par']}")
        print(f"[DATE] Date de saisie: {temps['manuel_date']}")

    # Afficher les détails des sources de données disponibles
    print(f"\n[DATA] Sources de donnees disponibles:")

    # Temps manuel
    if tache.temps_travail_manuel is not None:
        print(f"   * Temps manuel: {tache.temps_travail_manuel:.2f}h [UTILISE]")

    # Heures réelles des distributions
    heures_reelles = tache.distributions_charge.aggregate(
        total=Sum('heures_reelles')
    )['total']
    if heures_reelles and heures_reelles > 0:
        status_icon = "[UTILISE]" if temps['source'] == 'REEL' else ""
        print(f"   * Heures reelles (distributions): {heures_reelles:.2f}h {status_icon}")

    # Heures travaillées des participations
    heures_participation = tache.participations.aggregate(
        total=Sum('heures_travaillees')
    )['total']
    if heures_participation and heures_participation > 0:
        status_icon = "[UTILISE]" if temps['source'] == 'PARTICIPATION' else ""
        print(f"   * Heures travaillees (participations): {heures_participation:.2f}h {status_icon}")

    # Charge estimée
    if tache.charge_estimee_heures and tache.charge_estimee_heures > 0:
        status_icon = "[UTILISE]" if temps['source'] == 'ESTIME' else ""
        print(f"   * Charge estimee: {tache.charge_estimee_heures:.2f}h {status_icon}")

    # Heures planifiées
    heures_planifiees = tache.charge_totale_distributions
    if heures_planifiees > 0:
        status_icon = "[UTILISE]" if temps['source'] == 'PLANIFIE' else ""
        print(f"   * Heures planifiees (distributions): {heures_planifiees:.2f}h {status_icon}")

    if temps['source'] == 'AUCUNE':
        print(f"   [WARN] Aucune donnee disponible")

    print(f"{'-' * 80}")


def test_scenario_1_temps_manuel():
    """Test Scenario 1: Temps manuel (priorite absolue)"""
    print_separator()
    print("[TEST] SCENARIO 1: TEMPS MANUEL (Priorite Absolue)")
    print_separator()

    # Creer une tache terminee avec temps manuel
    tache = Tache.objects.filter(statut='TERMINEE').first()

    if not tache:
        print("[ERROR] Aucune tache terminee trouvee. Creez une tache terminee d'abord.")
        return None

    # Sauvegarder l'etat initial
    temps_manuel_initial = tache.temps_travail_manuel

    # Definir un temps manuel
    admin = Utilisateur.objects.filter(roles_utilisateur__role__nom_role='ADMIN').first()
    if admin:
        tache.temps_travail_manuel = 12.5
        tache.temps_travail_manuel_par = admin
        from django.utils import timezone
        tache.temps_travail_manuel_date = timezone.now()
        tache.save()

        print_temps_travail(tache, "Tache avec temps manuel")

        # Restaurer l'etat initial
        tache.temps_travail_manuel = temps_manuel_initial
        tache.temps_travail_manuel_par = None
        tache.temps_travail_manuel_date = None
        tache.save()
    else:
        print("[ERROR] Aucun admin trouve")

    return tache


def test_scenario_2_heures_reelles():
    """Test Scenario 2: Heures reelles des distributions"""
    print_separator()
    print("[TEST] SCENARIO 2: HEURES REELLES (Distributions)")
    print_separator()

    # Chercher une tache avec distributions ayant des heures reelles
    tache = Tache.objects.filter(
        statut='TERMINEE',
        distributions_charge__heures_reelles__gt=0,
        temps_travail_manuel__isnull=True
    ).first()

    if not tache:
        print("[ERROR] Aucune tache avec heures reelles trouvee.")
        print("[INFO] Conseil: Ajoutez des heures_reelles a une distribution de charge.")
        return None

    print_temps_travail(tache, "Tache avec heures reelles")
    return tache


def test_scenario_3_participations():
    """Test Scenario 3: Heures travaillees (participations)"""
    print_separator()
    print("[TEST] SCENARIO 3: HEURES TRAVAILLEES (Participations)")
    print_separator()

    # Chercher une tache avec participations
    tache = Tache.objects.filter(
        statut='TERMINEE',
        participations__heures_travaillees__gt=0,
        temps_travail_manuel__isnull=True,
        distributions_charge__heures_reelles__isnull=True
    ).first()

    if not tache:
        print("[ERROR] Aucune tache avec participations trouvee.")
        print("[INFO] Conseil: Ajoutez des participations avec heures_travaillees.")
        return None

    print_temps_travail(tache, "Tache avec participations")
    return tache


def test_scenario_4_charge_estimee():
    """Test Scenario 4: Charge estimee"""
    print_separator()
    print("[TEST] SCENARIO 4: CHARGE ESTIMEE")
    print_separator()

    # Chercher une tache avec charge estimee seulement
    tache = Tache.objects.filter(
        statut='TERMINEE',
        charge_estimee_heures__gt=0,
        temps_travail_manuel__isnull=True,
        distributions_charge__heures_reelles__isnull=True,
        participations__heures_travaillees__isnull=True
    ).first()

    if not tache:
        print("[ERROR] Aucune tache avec charge estimee seule trouvee.")
        return None

    print_temps_travail(tache, "Tache avec charge estimee")
    return tache


def test_scenario_5_heures_planifiees():
    """Test Scenario 5: Heures planifiees (fallback)"""
    print_separator()
    print("[TEST] SCENARIO 5: HEURES PLANIFIEES (Fallback)")
    print_separator()

    # Chercher une tache avec distributions planifiees seulement
    tache = Tache.objects.filter(
        statut='TERMINEE',
        distributions_charge__heures_planifiees__gt=0,
        temps_travail_manuel__isnull=True,
        charge_estimee_heures__isnull=True
    ).first()

    if not tache:
        print("[ERROR] Aucune tache avec heures planifiees seules trouvee.")
        return None

    print_temps_travail(tache, "Tache avec heures planifiees")
    return tache


def test_scenario_6_aucune_donnee():
    """Test Scenario 6: Aucune donnee"""
    print_separator()
    print("[TEST] SCENARIO 6: AUCUNE DONNEE")
    print_separator()

    # Chercher une tache terminee sans aucune donnee
    tache = Tache.objects.filter(
        statut='TERMINEE',
        temps_travail_manuel__isnull=True,
        charge_estimee_heures__isnull=True,
        distributions_charge__isnull=True
    ).first()

    if not tache:
        print("[ERROR] Aucune tache sans donnees trouvee.")
        print("[OK] Bon signe: Toutes les taches ont au moins une source de donnees!")
        return None

    print_temps_travail(tache, "Tache sans donnees")
    return tache


def print_summary():
    """Affiche un resume de toutes les taches terminees"""
    print_separator()
    print("[SUMMARY] RESUME: Toutes les taches terminees")
    print_separator()

    taches = Tache.objects.filter(statut='TERMINEE')[:10]

    if not taches:
        print("[ERROR] Aucune tache terminee trouvee dans la base de donnees.")
        return

    print(f"\n{'ID':<8} {'Ref':<25} {'Heures':<10} {'Source':<15} {'Fiable':<10}")
    print("-" * 80)

    total_heures = 0
    sources_count = {}

    for tache in taches:
        temps = tache.temps_travail_total
        ref = tache.reference or f"T-{tache.id}"
        fiable_str = "[OK] Oui" if temps['fiable'] else "[WARN] Non"

        print(f"{tache.id:<8} {ref[:24]:<25} {temps['heures']:<10.2f} {temps['source']:<15} {fiable_str:<10}")

        total_heures += temps['heures']
        sources_count[temps['source']] = sources_count.get(temps['source'], 0) + 1

    print("-" * 80)
    print(f"\n[TOTAL] {total_heures:.2f}h sur {taches.count()} taches")
    print(f"\n[STATS] Repartition par source:")
    for source, count in sorted(sources_count.items()):
        pct = (count / taches.count()) * 100
        print(f"   * {source}: {count} taches ({pct:.1f}%)")


def main():
    """Fonction principale"""
    print("\n")
    print("+" + "=" * 78 + "+")
    print("|" + " " * 78 + "|")
    print("|" + " " * 15 + "TEST TEMPS DE TRAVAIL TOTAL (Option 2)" + " " * 24 + "|")
    print("|" + " " * 78 + "|")
    print("+" + "=" * 78 + "+")

    # Vérifier qu'il y a des tâches dans la base
    nb_taches = Tache.objects.count()
    nb_terminees = Tache.objects.filter(statut='TERMINEE').count()

    print(f"\n[DATABASE] Base de donnees:")
    print(f"   * Total taches: {nb_taches}")
    print(f"   * Taches terminees: {nb_terminees}")

    if nb_terminees == 0:
        print("\n[ERROR] Aucune tache terminee dans la base de donnees.")
        print("[INFO] Creez des taches terminees pour tester cette fonctionnalite.")
        return

    # Exécuter tous les scénarios
    test_scenario_1_temps_manuel()
    test_scenario_2_heures_reelles()
    test_scenario_3_participations()
    test_scenario_4_charge_estimee()
    test_scenario_5_heures_planifiees()
    test_scenario_6_aucune_donnee()

    # Afficher le résumé
    print_summary()

    print_separator()
    print("[OK] TESTS TERMINES!")
    print_separator()
    print("\n[INFO] Pour utiliser cette fonctionnalite:")
    print("   1. GET /api/planification/taches/{id}/ -> Voir 'temps_travail_total'")
    print("   2. POST /api/planification/taches/{id}/set-temps-travail-manuel/")
    print("      Body: {\"heures\": 8.5}")
    print("   3. DELETE /api/planification/taches/{id}/reset-temps-travail-manuel/")
    print("\n")


if __name__ == "__main__":
    main()
