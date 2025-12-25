#!/usr/bin/env python
"""
Script pour peupler automatiquement le champ id_client des tâches
en se basant sur la relation indirecte: Tâche → Objets → Site → Client
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from api_planification.models import Tache
from django.db.models import Prefetch

def main():
    print("=" * 80)
    print("🔧 MISE À JOUR - Peuplement id_client des tâches")
    print("=" * 80)
    print()

    # Récupérer toutes les tâches sans client
    taches_sans_client = Tache.objects.prefetch_related(
        'objets__site__client'
    ).filter(
        deleted_at__isnull=True,
        id_client__isnull=True  # Seulement celles sans client
    )

    total = taches_sans_client.count()
    print(f"📊 Tâches à traiter: {total}")
    print()

    if total == 0:
        print("✅ Toutes les tâches ont déjà un client assigné !")
        print()
        return

    print("🔄 Traitement en cours...")
    print()

    updated = 0
    skipped_no_objects = 0
    skipped_no_site = 0
    skipped_no_client = 0
    errors = 0

    for i, tache in enumerate(taches_sans_client, 1):
        try:
            # Récupérer les objets de la tâche
            objets = tache.objets.select_related('site__client').all()

            if not objets.exists():
                skipped_no_objects += 1
                print(f"   [{i}/{total}] ⚠️  Tâche #{tache.id}: pas d'objets liés")
                continue

            # Trouver le premier objet avec site et client
            client_found = None
            for obj in objets:
                if obj.site and obj.site.client:
                    client_found = obj.site.client
                    break

            if client_found:
                tache.id_client = client_found
                tache.save(update_fields=['id_client'])
                updated += 1
                print(f"   [{i}/{total}] ✅ Tâche #{tache.id} → Client '{client_found.nom_structure}'")
            else:
                # Vérifier pourquoi
                has_site = any(obj.site is not None for obj in objets)
                if not has_site:
                    skipped_no_site += 1
                    print(f"   [{i}/{total}] ⚠️  Tâche #{tache.id}: objets sans site")
                else:
                    skipped_no_client += 1
                    print(f"   [{i}/{total}] ⚠️  Tâche #{tache.id}: sites sans client")

        except Exception as e:
            errors += 1
            print(f"   [{i}/{total}] ❌ Erreur tâche #{tache.id}: {e}")

    print()
    print("=" * 80)
    print("📊 RÉSUMÉ")
    print("=" * 80)
    print(f"   ✅ Tâches mises à jour: {updated}")
    print(f"   ⚠️  Ignorées (pas d'objets): {skipped_no_objects}")
    print(f"   ⚠️  Ignorées (objets sans site): {skipped_no_site}")
    print(f"   ⚠️  Ignorées (sites sans client): {skipped_no_client}")
    print(f"   ❌ Erreurs: {errors}")
    print()

    if updated > 0:
        print("✅ SUCCÈS ! Les tâches ont maintenant un client assigné.")
        print("   → Rechargez la page Planning dans le frontend")
        print("   → Le filtrage par client devrait maintenant fonctionner")
    else:
        print("⚠️  ATTENTION: Aucune tâche mise à jour")
        print()
        if skipped_no_objects > 0:
            print("   Problème: Les tâches n'ont pas d'objets liés")
            print("   Solution: Lors de la création des tâches,")
            print("            sélectionner au moins 1 objet inventaire")
        if skipped_no_site > 0:
            print("   Problème: Les objets n'ont pas de site assigné")
            print("   Solution: Vérifier l'intégrité des données objets")
        if skipped_no_client > 0:
            print("   Problème: Les sites n'ont pas de client assigné")
            print("   Solution: Django Admin > API > Sites")
            print("            Assigner chaque site à son client propriétaire")

    print()
    print("=" * 80)


if __name__ == '__main__':
    main()
