#!/usr/bin/env python
"""Verify task 79 with distributions."""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import Tache, DistributionCharge
import json

tache = Tache.objects.get(id=79)
distributions = DistributionCharge.objects.filter(tache=tache).order_by('date')

print("=" * 80)
print("TACHE #79 - VERIFICATION")
print("=" * 80)
print(f"\nType: {tache.id_type_tache.nom_tache}")
print(f"Client: {tache.id_client.utilisateur.get_full_name()}")
print(f"Structure: {tache.id_structure_client.nom}")
print(f"Equipe: {tache.id_equipe.nom_equipe}")
print(f"Periode: {tache.date_debut_planifiee.date()} -> {tache.date_fin_planifiee.date()}")
print(f"Charge estimee: {tache.charge_estimee_heures}h")
print(f"Statut: {tache.statut}")
print(f"Objets: {tache.objets.count()}")
print(f"\nDistributions de charge ({distributions.count()}):")
total = 0.0
for dist in distributions:
    total += dist.heures_planifiees
    print(f"  - {dist.date}: {dist.heures_planifiees}h ({dist.commentaire})")
print(f"\nTotal distributions: {total}h")
print(f"Charge via property: {tache.charge_totale_distributions}h")
print(f"Nombre jours travail: {tache.nombre_jours_travail}")
