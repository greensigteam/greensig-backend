#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de migration des données: Equipe.site -> Equipe.site_principal

Ce script migre les données de l'ancien champ 'site' vers le nouveau
système multi-sites (site_principal + sites_secondaires).

Usage:
    python migrate_equipe_sites.py

IMPORTANT: A executer APRES avoir applique la migration 0007.
"""

import os
import sys
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_users.models import Equipe


def migrate_equipe_sites():
    """
    Migre les donnees de site -> site_principal pour toutes les equipes.
    """
    print("=" * 80)
    print("MIGRATION: Equipe.site -> Equipe.site_principal")
    print("=" * 80)

    # Recuperer toutes les equipes qui ont un 'site' mais pas encore de 'site_principal'
    equipes_to_migrate = Equipe.objects.filter(
        site__isnull=False,
        site_principal__isnull=True
    )

    total = equipes_to_migrate.count()

    if total == 0:
        print("\n[OK] Aucune equipe a migrer. Toutes les equipes ont deja un site_principal.")
        return

    print(f"\n[INFO] {total} equipe(s) a migrer\n")

    migrated = 0
    errors = 0

    for equipe in equipes_to_migrate:
        try:
            print(f"  Migration: {equipe.nom_equipe}")
            print(f"    Ancien site: {equipe.site}")

            # Copier site -> site_principal
            equipe.site_principal = equipe.site
            equipe.save(update_fields=['site_principal'])

            print(f"    [OK] Nouveau site_principal: {equipe.site_principal}")
            migrated += 1

        except Exception as e:
            print(f"    [ERREUR] {e}")
            errors += 1

    print("\n" + "=" * 80)
    print(f"RESULTAT:")
    print(f"  [OK] Migrees avec succes: {migrated}")
    if errors > 0:
        print(f"  [ERREUR] Erreurs: {errors}")
    print("=" * 80)

    if migrated > 0:
        print("\n[IMPORTANT]:")
        print("  1. Verifiez que les donnees sont correctes dans l'admin Django")
        print("  2. Une fois valide, l'ancien champ 'site' pourra etre supprime")
        print("     dans une prochaine migration")


if __name__ == '__main__':
    try:
        migrate_equipe_sites()
        print("\n[OK] Migration terminee avec succes!")
    except Exception as e:
        print(f"\n[ERREUR CRITIQUE] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
