#!/usr/bin/env python
"""Script pour analyser les performances des requêtes API."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from django.db import connection, reset_queries
from django.test.utils import override_settings
from api_users.models import Equipe

print("\n" + "="*80)
print("ANALYSE DE PERFORMANCE - API Equipes")
print("="*80)

# Test 1: Liste des équipes (queryset de base)
reset_queries()
with override_settings(DEBUG=True):
    equipes = list(Equipe.objects.all())
    print(f"\n1. QUERYSET DE BASE (Equipe.objects.all())")
    print(f"   Nombre d'equipes: {len(equipes)}")
    print(f"   Nombre de requetes SQL: {len(connection.queries)}")
    if connection.queries:
        print(f"\n   Premiere requete:")
        print(f"   {connection.queries[0]['sql'][:200]}")

# Test 2: Propriété calculée (nombre_membres)
reset_queries()
with override_settings(DEBUG=True):
    equipes = Equipe.objects.all()
    for equipe in equipes:
        _ = equipe.nombre_membres  # Propriété calculée

    print(f"\n2. AVEC PROPRIETE CALCULEE (nombre_membres)")
    print(f"   Nombre d'equipes: {equipes.count()}")
    print(f"   Nombre de requetes SQL: {len(connection.queries)}")
    print(f"   ⚠️ N+1 sur nombre_membres!" if len(connection.queries) > 5 else "   ✅ Pas de N+1")

# Test 3: Accès aux relations (simulation serializer)
reset_queries()
with override_settings(DEBUG=True):
    equipes = Equipe.objects.all()
    for equipe in equipes:
        # Simulation de ce que fait le serializer
        _ = equipe.chef_equipe  # Accès ForeignKey
        if equipe.chef_equipe:
            _ = equipe.chef_equipe.nom_complet  # Propriété
        _ = equipe.superviseur  # Accès ForeignKey
        if equipe.superviseur:
            _ = equipe.superviseur.utilisateur.get_full_name()  # Double relation!

    print(f"\n3. AVEC ACCES AUX RELATIONS (simulation serializer)")
    print(f"   Nombre d'equipes: {equipes.count()}")
    print(f"   Nombre de requetes SQL: {len(connection.queries)}")
    print(f"   ⚠️ PROBLEME N+1 DETECTE!" if len(connection.queries) > 10 else "   ✅ Pas de N+1")

# Test 4: Avec select_related (optimisé)
reset_queries()
with override_settings(DEBUG=True):
    equipes = Equipe.objects.select_related(
        'chef_equipe',
        'superviseur',
        'superviseur__utilisateur'
    ).all()

    for equipe in equipes:
        _ = equipe.chef_equipe
        if equipe.chef_equipe:
            _ = equipe.chef_equipe.nom_complet
        _ = equipe.superviseur
        if equipe.superviseur:
            _ = equipe.superviseur.utilisateur.get_full_name()

    print(f"\n4. AVEC SELECT_RELATED (optimise)")
    print(f"   Nombre d'equipes: {len(list(equipes))}")
    print(f"   Nombre de requetes SQL: {len(connection.queries)}")
    print(f"   ✅ OPTIMISE!" if len(connection.queries) <= 2 else f"   ⚠️ Encore {len(connection.queries)} requetes")

print("\n" + "="*80)
print("RECOMMANDATIONS:")
print("="*80)
print("1. Ajouter select_related() dans EquipeViewSet.get_queryset()")
print("2. Utiliser prefetch_related() pour les relations ManyToMany")
print("3. Activer le cache pour reduire les requetes repetitives")
print("="*80 + "\n")
