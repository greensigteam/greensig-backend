"""
Script GLOBAL pour nettoyer TOUTES les données de la base GreenSIG
Usage: python clear_all_database.py [--force]

ATTENTION: Ce script supprime TOUTES les données de toutes les tables !
"""

import os
import sys
import django
from pathlib import Path

# Configuration Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from django.db import connection
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

# Import all models
from api.models import (
    Site, SousSite, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon, Objet,
    Notification
)
from api_users.models import (
    Utilisateur, Client, Superviseur, Operateur, Equipe,
    Competence, CompetenceOperateur, Absence, StructureClient
)
from api_planification.models import Tache, ParticipationTache, TypeTache
from api_reclamations.models import Reclamation, TypeReclamation, Urgence
from api_suivi_taches.models import Produit, ProduitMatiereActive, DoseProduit, ConsommationProduit, Photo


def print_header():
    print("\n" + "=" * 70)
    print(" " * 15 + "NETTOYAGE GLOBAL - BASE DE DONNÉES GREENSIG")
    print("=" * 70)
    print("\n⚠️  ATTENTION: Ce script va SUPPRIMER TOUTES LES DONNÉES !")
    print("    - Utilisateurs (sauf superuser)")
    print("    - Clients, Superviseurs, Opérateurs")
    print("    - Équipes, Compétences, Absences")
    print("    - Sites, Sous-sites, Objets GIS")
    print("    - Tâches, Planification")
    print("    - Réclamations")
    print("    - Photos, Consommations, Produits")
    print("    - Notifications")
    print("\n" + "=" * 70 + "\n")


def clear_all_data(keep_superuser=True, keep_config=True):
    """Supprime toutes les données dans l'ordre correct (respect des FK)"""

    total_deleted = 0

    # Ordre de suppression (respecte les foreign keys)
    models_to_clear = [
        # 1. Notifications
        ("Notifications", Notification),

        # 2. Suivi des tâches (dépend de Tache)
        ("Photos", Photo),
        ("Consommations produits", ConsommationProduit),

        # 3. Planification (dépend de Tache, Operateur, Equipe)
        ("Participations tâches", ParticipationTache),
        ("Tâches", Tache),

        # 4. Réclamations
        ("Réclamations", Reclamation),

        # 5. Compétences opérateurs (dépend de Operateur, Competence)
        ("Compétences opérateurs", CompetenceOperateur),

        # 6. Absences (dépend de Operateur)
        ("Absences", Absence),

        # 7. Opérateurs (dépend de Equipe, Superviseur)
        ("Opérateurs", Operateur),

        # 8. Équipes (dépend de Site)
        ("Équipes", Equipe),

        # 9. Superviseurs (dépend de Utilisateur)
        ("Superviseurs", Superviseur),

        # 10. Clients (dépend de Utilisateur, StructureClient)
        ("Clients", Client),

        # 11. Objets GIS (dépend de Site, SousSite)
        ("Arbres", Arbre),
        ("Gazons", Gazon),
        ("Palmiers", Palmier),
        ("Arbustes", Arbuste),
        ("Vivaces", Vivace),
        ("Cactus", Cactus),
        ("Graminées", Graminee),
        ("Puits", Puit),
        ("Pompes", Pompe),
        ("Vannes", Vanne),
        ("Clapets", Clapet),
        ("Canalisations", Canalisation),
        ("Aspersions", Aspersion),
        ("Goutte-à-goutte", Goutte),
        ("Ballons", Ballon),

        # 12. Hiérarchie spatiale
        ("Sous-sites", SousSite),
        ("Sites", Site),

        # 13. Structures clients
        ("Structures clients", StructureClient),
    ]

    print("🗑️  Suppression des données...\n")

    for name, model in models_to_clear:
        try:
            count = model.objects.count()
            if count > 0:
                model.objects.all().delete()
                print(f"  ✓ {name:30} : {count:>6} supprimé(s)")
                total_deleted += count
            else:
                print(f"    {name:30} : {'vide':>6}")
        except Exception as e:
            print(f"  ✗ {name:30} : ERREUR - {str(e)[:40]}")

    # Utilisateurs (optionnel - garde superuser)
    print()
    if keep_superuser:
        User = get_user_model()
        user_count = User.objects.filter(is_superuser=False).count()
        if user_count > 0:
            User.objects.filter(is_superuser=False).delete()
            print(f"  ✓ {'Utilisateurs (non-superuser)':30} : {user_count:>6} supprimé(s)")
            total_deleted += user_count
        else:
            print(f"    {'Utilisateurs (non-superuser)':30} : {'vide':>6}")

        superuser_count = User.objects.filter(is_superuser=True).count()
        print(f"  🔒 {'Superusers conservés':30} : {superuser_count:>6}")
    else:
        User = get_user_model()
        user_count = User.objects.count()
        if user_count > 0:
            User.objects.all().delete()
            print(f"  ✓ {'Tous les utilisateurs':30} : {user_count:>6} supprimé(s)")
            total_deleted += user_count

    # Tables de configuration (optionnel)
    if not keep_config:
        config_models = [
            ("Types de tâches", TypeTache),
            ("Compétences", Competence),
            ("Types de réclamation", TypeReclamation),
            ("Niveaux d'urgence", Urgence),
            ("Doses produits", DoseProduit),
            ("Matières actives", ProduitMatiereActive),
            ("Produits", Produit),
        ]
        print()
        for name, model in config_models:
            try:
                count = model.objects.count()
                if count > 0:
                    model.objects.all().delete()
                    print(f"  ✓ {name:30} : {count:>6} supprimé(s)")
                    total_deleted += count
            except Exception as e:
                print(f"  ✗ {name:30} : ERREUR - {str(e)[:40]}")
    else:
        print(f"\n  🔒 Tables de configuration conservées (types tâches, compétences, urgences...)")

    return total_deleted


def reset_sequences():
    """Réinitialise les séquences auto-increment PostgreSQL"""
    print("\n🔄 Réinitialisation des séquences...")

    with connection.cursor() as cursor:
        # Get all sequences
        cursor.execute("""
            SELECT sequence_name FROM information_schema.sequences
            WHERE sequence_schema = 'public'
        """)
        sequences = cursor.fetchall()

        for (seq_name,) in sequences:
            try:
                cursor.execute(f"ALTER SEQUENCE {seq_name} RESTART WITH 1")
            except:
                pass  # Ignore errors for sequences that don't exist

    print("  ✓ Séquences réinitialisées")


def main():
    """Fonction principale avec confirmations multiples"""
    force_mode = '--force' in sys.argv
    delete_all = '--delete-all' in sys.argv

    print_header()

    if not force_mode:
        print("Options disponibles:")
        print("  --force       : Pas de confirmation (DANGEREUX)")
        print("  --delete-all  : Supprimer aussi les superusers et config\n")

        response = input("Êtes-vous sûr de vouloir continuer ? (oui/non) : ")
        if response.lower() not in ['oui', 'o', 'yes', 'y']:
            print("\n✗ Opération annulée.\n")
            return

        response = input("\n⚠️  DERNIÈRE CONFIRMATION - Tapez 'SUPPRIMER TOUT' : ")
        if response != 'SUPPRIMER TOUT':
            print("\n✗ Opération annulée.\n")
            return

    print()
    total = clear_all_data(
        keep_superuser=not delete_all,
        keep_config=not delete_all
    )

    reset_sequences()

    print("\n" + "=" * 70)
    print(f"  TOTAL : {total} enregistrements supprimés")
    print("=" * 70)
    print("\n✓ Base de données nettoyée avec succès.\n")


if __name__ == '__main__':
    main()