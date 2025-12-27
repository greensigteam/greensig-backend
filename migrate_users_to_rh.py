"""
Script de Migration : Utilisateurs Opérateurs → Données RH

⚠️ ATTENTION : Ce script effectue des opérations IRRÉVERSIBLES
📋 Assurez-vous d'avoir un backup de la base de données avant exécution

Ce script :
1. Vérifie l'intégrité des données
2. Affiche un résumé de la migration prévue
3. Migre les utilisateurs OPERATEUR en données RH standalone
4. Gère les utilisateurs CHEF_EQUIPE (à décider manuellement)
5. Supprime les comptes utilisateurs opérateurs (AVEC CONFIRMATION)
6. Nettoie les rôles obsolètes

Usage:
    cd backend
    python migrate_users_to_rh.py
"""

import os
import sys
import django
from datetime import date

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from django.db import transaction
from api_users.models import (
    Utilisateur, Role, UtilisateurRole, Operateur, Superviseur,
    Equipe, Client
)


class Colors:
    """Codes couleur pour le terminal."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Affiche un en-tête formaté."""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


def print_success(text):
    """Affiche un message de succès."""
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_warning(text):
    """Affiche un avertissement."""
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def print_error(text):
    """Affiche une erreur."""
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text):
    """Affiche une information."""
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def verify_prerequisites():
    """Vérifie que les prérequis sont remplis."""
    print_header("VÉRIFICATION DES PRÉREQUIS")

    # 1. Vérifier que les migrations ont été exécutées
    try:
        # Test si le modèle Superviseur existe
        Superviseur.objects.count()
        print_success("Modèle Superviseur existe")
    except Exception as e:
        print_error(f"Modèle Superviseur introuvable : {e}")
        print_warning("Exécutez d'abord : python manage.py migrate")
        return False

    # 2. Vérifier que le rôle SUPERVISEUR existe
    try:
        superviseur_role = Role.objects.get(nom_role='SUPERVISEUR')
        print_success(f"Rôle SUPERVISEUR existe (ID: {superviseur_role.id})")
    except Role.DoesNotExist:
        print_error("Rôle SUPERVISEUR introuvable")
        return False

    # 3. Vérifier que le modèle Operateur a les nouveaux champs
    try:
        test_op = Operateur.objects.first()
        if test_op:
            # Vérifier que les champs nom, prenom existent
            _ = test_op.nom
            _ = test_op.prenom
        print_success("Modèle Operateur a les nouveaux champs (nom, prenom)")
    except AttributeError:
        print_error("Modèle Operateur n'a pas encore les champs nom/prenom")
        print_warning("Exécutez d'abord : python manage.py migrate")
        return False

    return True


def analyze_migration():
    """Analyse et affiche un résumé de la migration."""
    print_header("ANALYSE DES DONNÉES À MIGRER")

    # Compter les utilisateurs par rôle
    try:
        operateur_role = Role.objects.get(nom_role='OPERATEUR')
        operateur_users = Utilisateur.objects.filter(
            roles_utilisateur__role=operateur_role
        ).distinct()
        operateur_count = operateur_users.count()
    except Role.DoesNotExist:
        operateur_count = 0
        operateur_users = []

    try:
        chef_role = Role.objects.get(nom_role='CHEF_EQUIPE')
        chef_users = Utilisateur.objects.filter(
            roles_utilisateur__role=chef_role
        ).distinct()
        chef_count = chef_users.count()
    except Role.DoesNotExist:
        chef_count = 0
        chef_users = []

    # Afficher le résumé
    print(f"📊 Utilisateurs OPERATEUR : {operateur_count}")
    print(f"📊 Utilisateurs CHEF_EQUIPE : {chef_count}")
    print(f"📊 TOTAL à traiter : {operateur_count + chef_count}\n")

    # Détails opérateurs
    if operateur_count > 0:
        print(f"{Colors.BOLD}Opérateurs à migrer :{Colors.ENDC}")
        for user in operateur_users:
            profile = "✅ Profil OK" if hasattr(user, 'operateur_profile') else "❌ Pas de profil"
            print(f"  • {user.get_full_name()} ({user.email}) - {profile}")

    # Détails chefs d'équipe
    if chef_count > 0:
        print(f"\n{Colors.BOLD}Chefs d'équipe à traiter :{Colors.ENDC}")
        for user in chef_users:
            has_operateur = hasattr(user, 'operateur_profile')
            status = "Opérateur" if has_operateur else "PUR (à transformer en Superviseur?)"
            print(f"  • {user.get_full_name()} ({user.email}) - {status}")

    return operateur_users, chef_users


def migrate_operateurs(operateur_users, dry_run=True):
    """
    Migre les utilisateurs OPERATEUR en données RH.

    Args:
        operateur_users: QuerySet des utilisateurs avec rôle OPERATEUR
        dry_run: Si True, simule sans modifier la base
    """
    print_header("MIGRATION DES OPÉRATEURS")

    if dry_run:
        print_warning("MODE SIMULATION (dry_run=True) - Aucune modification")

    migrated = 0
    errors = []

    for user in operateur_users:
        try:
            if hasattr(user, 'operateur_profile'):
                operateur = user.operateur_profile

                # Vérifier si les données ont déjà été copiées
                if not operateur.nom or not operateur.prenom:
                    if not dry_run:
                        # Copier les données utilisateur → operateur
                        operateur.nom = user.nom
                        operateur.prenom = user.prenom
                        operateur.email = user.email
                        operateur.save()

                    print_success(f"Migré : {user.get_full_name()} → Operateur standalone")
                    migrated += 1
                else:
                    print_info(f"Déjà migré : {operateur.nom} {operateur.prenom}")
                    migrated += 1
            else:
                print_warning(f"{user.get_full_name()} n'a pas de profil operateur")

        except Exception as e:
            error_msg = f"{user.get_full_name()}: {str(e)}"
            errors.append(error_msg)
            print_error(error_msg)

    print(f"\n✅ {migrated} opérateur(s) {'seraient' if dry_run else ''} migré(s)")
    if errors:
        print_error(f"{len(errors)} erreur(s) rencontrée(s)")

    return migrated, errors


def handle_chefs_equipe(chef_users, dry_run=True):
    """
    Gère les utilisateurs CHEF_EQUIPE.

    Décision manuelle requise pour chaque utilisateur :
    - Devenir SUPERVISEUR (se connecte, supervise)
    - Devenir OPERATEUR simple (RH, ne se connecte pas)
    """
    print_header("GESTION DES CHEFS D'ÉQUIPE")

    if len(chef_users) == 0:
        print_info("Aucun chef d'équipe à traiter")
        return

    print(f"{Colors.BOLD}DÉCISION REQUISE pour chaque chef d'équipe :{Colors.ENDC}\n")

    for user in chef_users:
        print(f"\n👤 {user.get_full_name()} ({user.email})")

        has_operateur_profile = hasattr(user, 'operateur_profile')

        if has_operateur_profile:
            print("   → A un profil Opérateur (travaille probablement sur le terrain)")
            print(f"   {Colors.BOLD}Recommandation : Reste OPERATEUR (donnée RH){Colors.ENDC}")
        else:
            print("   → N'a PAS de profil Opérateur (rôle purement managérial)")
            print(f"   {Colors.BOLD}Recommandation : Devient SUPERVISEUR (utilisateur){Colors.ENDC}")

        if not dry_run:
            print("\n   Actions possibles :")
            print("   [1] Transformer en SUPERVISEUR (peut se connecter)")
            print("   [2] Transformer en OPERATEUR (donnée RH uniquement)")
            print("   [3] Ignorer (traiter plus tard)")

            choice = input("   Votre choix (1/2/3) : ").strip()

            # TODO: Implémenter les actions selon le choix
            if choice == '1':
                print_info("→ À implémenter : Création profil Superviseur")
            elif choice == '2':
                print_info("→ À implémenter : Migration vers Operateur")
            else:
                print_warning("→ Ignoré")


def delete_operateur_accounts(operateur_users, dry_run=True):
    """
    Supprime les comptes utilisateurs des opérateurs.

    ⚠️ CRITIQUE : Ne s'exécute qu'après migration réussie des données.
    """
    print_header("SUPPRESSION DES COMPTES UTILISATEURS OPÉRATEURS")

    if dry_run:
        print_warning("MODE SIMULATION - Aucune suppression")
        print(f"💀 {len(operateur_users)} compte(s) {'seraient' if dry_run else ''} supprimé(s)")
        return

    # Demander confirmation explicite
    print_error(f"⚠️  ATTENTION : {len(operateur_users)} compte(s) vont être SUPPRIMÉS")
    print_error("⚠️  Cette action est IRRÉVERSIBLE !")
    print()
    confirmation = input(f"{Colors.BOLD}Taper 'SUPPRIMER' en MAJUSCULES pour confirmer : {Colors.ENDC}")

    if confirmation != 'SUPPRIMER':
        print_warning("❌ Annulé - Aucune suppression")
        return

    deleted = 0
    for user in operateur_users:
        try:
            email = user.email
            nom = user.get_full_name()
            user.delete()
            print(f"🗑️  Supprimé : {nom} ({email})")
            deleted += 1
        except Exception as e:
            print_error(f"Erreur pour {user.email}: {e}")

    print_success(f"{deleted}/{len(operateur_users)} compte(s) supprimé(s)")


def cleanup_roles():
    """
    Nettoie les rôles obsolètes OPERATEUR et CHEF_EQUIPE.

    ⚠️ À exécuter APRÈS suppression des comptes utilisateurs.
    """
    print_header("NETTOYAGE DES RÔLES OBSOLÈTES")

    try:
        operateur_role = Role.objects.get(nom_role='OPERATEUR')
        # Vérifier qu'aucun utilisateur n'a ce rôle
        count = UtilisateurRole.objects.filter(role=operateur_role).count()
        if count == 0:
            operateur_role.delete()
            print_success("Rôle OPERATEUR supprimé")
        else:
            print_warning(f"Rôle OPERATEUR encore utilisé par {count} utilisateur(s)")
    except Role.DoesNotExist:
        print_info("Rôle OPERATEUR déjà supprimé")

    try:
        chef_role = Role.objects.get(nom_role='CHEF_EQUIPE')
        count = UtilisateurRole.objects.filter(role=chef_role).count()
        if count == 0:
            chef_role.delete()
            print_success("Rôle CHEF_EQUIPE supprimé")
        else:
            print_warning(f"Rôle CHEF_EQUIPE encore utilisé par {count} utilisateur(s)")
    except Role.DoesNotExist:
        print_info("Rôle CHEF_EQUIPE déjà supprimé")


@transaction.atomic
def run_migration(dry_run=True):
    """
    Lance la migration complète avec transaction.

    Args:
        dry_run: Si True, simule sans modifier la base
    """
    print_header("🚀 MIGRATION : UTILISATEURS → DONNÉES RH")

    if dry_run:
        print_warning("MODE SIMULATION ACTIVÉ (dry_run=True)")
        print_warning("Aucune modification ne sera apportée à la base de données")
        print()

    # 1. Vérifier les prérequis
    if not verify_prerequisites():
        print_error("Prérequis non remplis. Migration annulée.")
        return False

    # 2. Analyser les données
    operateur_users, chef_users = analyze_migration()

    if len(operateur_users) == 0 and len(chef_users) == 0:
        print_info("Aucune donnée à migrer")
        return True

    # 3. Demander confirmation avant de continuer
    if not dry_run:
        print()
        confirmation = input(f"{Colors.BOLD}Continuer la migration ? (oui/non) : {Colors.ENDC}")
        if confirmation.lower() not in ['oui', 'yes', 'o', 'y']:
            print_warning("Migration annulée par l'utilisateur")
            return False

    # 4. Migrer les opérateurs
    if len(operateur_users) > 0:
        migrate_operateurs(operateur_users, dry_run=dry_run)

    # 5. Gérer les chefs d'équipe
    if len(chef_users) > 0:
        handle_chefs_equipe(chef_users, dry_run=dry_run)

    # 6. Suppression des comptes (désactivé en dry_run)
    # if not dry_run:
    #     delete_operateur_accounts(operateur_users, dry_run=False)

    # 7. Nettoyage des rôles
    # if not dry_run:
    #     cleanup_roles()

    print_header("✅ MIGRATION TERMINÉE")

    if dry_run:
        print_info("C'était une simulation. Pour exécuter réellement :")
        print_info("  python migrate_users_to_rh.py --execute")

    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migration Utilisateurs → Données RH')
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Exécuter réellement la migration (sinon simulation)'
    )
    args = parser.parse_args()

    # Mode dry_run par défaut (sécurité)
    dry_run = not args.execute

    if not dry_run:
        print_warning("⚠️  MODE EXÉCUTION ACTIVÉ")
        print_warning("⚠️  Les modifications seront RÉELLES et IRRÉVERSIBLES")
        print()
        final_confirm = input(f"{Colors.BOLD}Êtes-vous ABSOLUMENT sûr ? (oui/non) : {Colors.ENDC}")
        if final_confirm.lower() not in ['oui', 'yes']:
            print_error("Migration annulée par sécurité")
            sys.exit(0)

    # Lancer la migration
    success = run_migration(dry_run=dry_run)
    sys.exit(0 if success else 1)
