#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test des statistiques RH pour le CLIENT"""
import os
import sys
import django

# Fix encoding for Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from django.test import RequestFactory
from api_users.models import Utilisateur
from api_users.views import StatistiquesUtilisateursView

print("\n" + "="*70)
print("TEST DES STATISTIQUES RH POUR LE CLIENT")
print("="*70)

try:
    # Trouver un utilisateur CLIENT
    client_user = Utilisateur.objects.filter(roles_utilisateur__role__nom_role='CLIENT').first()
    if not client_user:
        print('\n❌ Aucun CLIENT trouvé')
        exit(1)

    print(f'\n✅ CLIENT trouvé: {client_user.email}')

    # Créer une fausse requête HTTP
    factory = RequestFactory()
    request = factory.get('/api/users/statistiques/')
    request.user = client_user

    # Appeler la vue
    view = StatistiquesUtilisateursView()
    response = view.get(request)

    # Afficher les statistiques
    stats = response.data

    print(f'\n📊 STATISTIQUES RETOURNÉES:')
    print(f'\n👥 Opérateurs:')
    print(f'   - Total: {stats["operateurs"]["total"]}')
    print(f'   - Actifs: {stats["operateurs"]["actifs"]}')
    print(f'   - Disponibles aujourd\'hui: {stats["operateurs"]["disponibles_aujourdhui"]}')
    print(f'   - Chefs d\'équipe: {stats["operateurs"]["chefs_equipe"]}')

    print(f'\n🏢 Équipes:')
    print(f'   - Total: {stats["equipes"]["total"]}')
    print(f'   - Actives: {stats["equipes"]["actives"]}')
    print(f'   - Statuts opérationnels:')
    print(f'      * Complètes: {stats["equipes"]["statuts_operationnels"]["completes"]}')
    print(f'      * Partielles: {stats["equipes"]["statuts_operationnels"]["partielles"]}')
    print(f'      * Indisponibles: {stats["equipes"]["statuts_operationnels"]["indisponibles"]}')

    print(f'\n🏖️ Absences:')
    print(f'   - En attente: {stats["absences"]["en_attente"]}')
    print(f'   - En cours: {stats["absences"]["en_cours"]}')

    if stats["equipes"]["total"] > 0 or stats["operateurs"]["total"] > 0:
        print(f'\n✅ SUCCÈS ! Le CLIENT peut voir les statistiques de ses équipes/opérateurs')
    else:
        print(f'\n⚠️ Aucune donnée pour ce CLIENT (normal si aucune équipe assignée)')

except Exception as e:
    print(f'\n❌ ERREUR: {e}')
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("FIN DU TEST")
print("="*70 + "\n")
