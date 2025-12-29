#!/usr/bin/env python
"""Test du nouveau filtrage pour les tâches sans équipe"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import Tache
from api_users.models import Utilisateur, Superviseur
from django.db.models import Q

print("\n" + "="*70)
print("TEST DU NOUVEAU FILTRAGE DES TACHES")
print("="*70)

# Trouver un superviseur
superviseurs = Utilisateur.objects.filter(
    roles_utilisateur__role__nom_role='SUPERVISEUR'
).prefetch_related('superviseur_profile')

if not superviseurs.exists():
    print("\n⚠️  Aucun SUPERVISEUR en base. Impossible de tester.")
else:
    user = superviseurs.first()
    superviseur = user.superviseur_profile

    print(f"\n1. SUPERVISEUR: {user.get_full_name()}")
    print(f"   Sites supervisés: {superviseur.equipes_gerees.count()} équipes")

    # Appliquer le nouveau filtrage
    print("\n2. FILTRAGE APPLIQUÉ:")

    # Critère 1: Tâches avec équipes
    taches_avec_equipes = Q(equipes__site__superviseur=superviseur) | Q(id_equipe__site__superviseur=superviseur)
    count_avec_equipes = Tache.objects.filter(deleted_at__isnull=True).filter(taches_avec_equipes).distinct().count()
    print(f"   Tâches assignées à des équipes: {count_avec_equipes}")

    # Critère 2: Tâches sans équipe mais sur ses sites
    taches_sans_equipe = Q(
        equipes__isnull=True,
        id_equipe__isnull=True,
        objets__site__superviseur=superviseur
    )

    # Compter les tâches sans équipe sur ses sites
    taches_sans_eq = Tache.objects.filter(deleted_at__isnull=True).filter(
        Q(equipes__isnull=True) | Q(equipes__id__isnull=True)
    ).filter(
        id_equipe__isnull=True
    ).filter(
        objets__site__superviseur=superviseur
    ).distinct()

    count_sans_equipes = taches_sans_eq.count()
    print(f"   Tâches SANS équipe sur ses sites: {count_sans_equipes}")

    if count_sans_equipes > 0:
        print("\n   Détail des tâches sans équipe:")
        for t in taches_sans_eq:
            objets = list(t.objets.values_list('id', flat=True))
            print(f"      - Tâche #{t.id}: {t.id_type_tache.nom_tache}")
            print(f"        Objets: {objets}")
            print(f"        Équipes M2M: {t.equipes.count()}")
            print(f"        Équipe legacy: {t.id_equipe}")

    # Total visible
    total = Tache.objects.filter(deleted_at__isnull=True).filter(
        taches_avec_equipes | taches_sans_equipe
    ).distinct().count()

    print(f"\n3. TOTAL VISIBLE: {total} tâches")
    print(f"   = {count_avec_equipes} (avec équipes) + {count_sans_equipes} (sans équipe)")

print("\n" + "="*70)
