#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test de validation des dates de reclamations"""
import os
import sys
import django
from datetime import timedelta

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from django.utils import timezone
from django.core.exceptions import ValidationError
from api_reclamations.models import Reclamation, TypeReclamation, Urgence

print("\n" + "="*70)
print("TEST DE VALIDATION DES DATES DE RECLAMATION")
print("="*70)

# Recuperer des donnees de test
try:
    type_rec = TypeReclamation.objects.filter(actif=True).first()
    urgence = Urgence.objects.first()

    if not type_rec or not urgence:
        print("\n[ERREUR] Pas de donnees de test (TypeReclamation ou Urgence)")
        print("   Executez d'abord les commandes de seed de donnees")
        exit(1)

    print(f"\n1. DONNEES DE TEST:")
    print(f"   Type: {type_rec.nom_reclamation}")
    print(f"   Urgence: {urgence.niveau_urgence}")

    # Test 1: Date actuelle (OK)
    print("\n2. TEST 1: Date de constatation = MAINTENANT (devrait reussir)")
    try:
        rec1 = Reclamation(
            type_reclamation=type_rec,
            urgence=urgence,
            description="Test date actuelle",
            date_constatation=timezone.now()
        )
        rec1.full_clean()  # Valide avec clean()
        print("   [OK] SUCCES: Date actuelle acceptee")
    except ValidationError as e:
        print(f"   [KO] ECHEC: {e}")

    # Test 2: Date dans le futur (ERREUR attendue)
    print("\n3. TEST 2: Date de constatation = FUTUR +1 jour (devrait echouer)")
    try:
        rec2 = Reclamation(
            type_reclamation=type_rec,
            urgence=urgence,
            description="Test date future",
            date_constatation=timezone.now() + timedelta(days=1)
        )
        rec2.full_clean()
        print("   [KO] ECHEC: Date future acceptee (ne devrait pas !)")
    except ValidationError as e:
        print(f"   [OK] SUCCES: Date future rejetee")
        print(f"      Message: {e.message_dict.get('date_constatation', [''])[0]}")

    # Test 3: Date trop ancienne (ERREUR attendue)
    print("\n4. TEST 3: Date de constatation = -100 jours (devrait echouer)")
    try:
        rec3 = Reclamation(
            type_reclamation=type_rec,
            urgence=urgence,
            description="Test date ancienne",
            date_constatation=timezone.now() - timedelta(days=100)
        )
        rec3.full_clean()
        print("   [KO] ECHEC: Date ancienne acceptee (ne devrait pas !)")
    except ValidationError as e:
        print(f"   [OK] SUCCES: Date trop ancienne rejetee")
        print(f"      Message: {e.message_dict.get('date_constatation', [''])[0]}")

    # Test 4: Date a la limite (89 jours) (OK)
    print("\n5. TEST 4: Date de constatation = -89 jours (devrait reussir)")
    try:
        rec4 = Reclamation(
            type_reclamation=type_rec,
            urgence=urgence,
            description="Test date limite",
            date_constatation=timezone.now() - timedelta(days=89)
        )
        rec4.full_clean()
        print("   [OK] SUCCES: Date limite acceptee (89 jours)")
    except ValidationError as e:
        print(f"   [KO] ECHEC: {e}")

    # Test 5: Date par defaut (automatique)
    print("\n6. TEST 5: Date de constatation NON FOURNIE (auto = now)")
    rec5 = Reclamation(
        type_reclamation=type_rec,
        urgence=urgence,
        description="Test date auto"
    )
    print(f"   [OK] SUCCES: Date automatique = {rec5.date_constatation}")

except Exception as e:
    print(f"\n[KO] ERREUR GENERALE: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("FIN DES TESTS")
print("="*70 + "\n")
