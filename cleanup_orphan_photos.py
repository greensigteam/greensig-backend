#!/usr/bin/env python
"""
Script de nettoyage des photos orphelines.

Identifie et supprime les enregistrements Photo dont les fichiers
n'existent plus sur le disque.

Usage:
    python cleanup_orphan_photos.py          # Mode dry-run (affiche seulement)
    python cleanup_orphan_photos.py --delete # Supprime les enregistrements orphelins
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.conf import settings
from api_suivi_taches.models import Photo


def find_orphan_photos():
    """Trouve toutes les photos dont le fichier n'existe pas."""
    orphans = []

    for photo in Photo.objects.all():
        if photo.fichier:
            file_path = os.path.join(settings.MEDIA_ROOT, str(photo.fichier))
            if not os.path.exists(file_path):
                orphans.append({
                    'id': photo.id,
                    'fichier': str(photo.fichier),
                    'type_photo': photo.type_photo,
                    'tache_id': photo.tache_id,
                    'date_prise': photo.date_prise,
                })

    return orphans


def cleanup_orphan_photos(dry_run=True):
    """
    Nettoie les photos orphelines.

    Args:
        dry_run: Si True, affiche seulement sans supprimer.
    """
    orphans = find_orphan_photos()

    if not orphans:
        print("✅ Aucune photo orpheline trouvée.")
        return 0

    print(f"\n{'=' * 60}")
    print(f"📷 {len(orphans)} photo(s) orpheline(s) trouvée(s)")
    print(f"{'=' * 60}\n")

    for photo in orphans:
        print(f"  ID: {photo['id']}")
        print(f"  Fichier: {photo['fichier']}")
        print(f"  Type: {photo['type_photo']}")
        print(f"  Tâche ID: {photo['tache_id']}")
        print(f"  Date: {photo['date_prise']}")
        print(f"  {'-' * 40}")

    if dry_run:
        print(f"\n⚠️  Mode DRY-RUN: Aucune suppression effectuée.")
        print(f"   Relancez avec --delete pour supprimer ces enregistrements.")
    else:
        # Suppression
        ids_to_delete = [p['id'] for p in orphans]
        deleted_count, _ = Photo.objects.filter(id__in=ids_to_delete).delete()
        print(f"\n✅ {deleted_count} enregistrement(s) supprimé(s) de la base de données.")

    return len(orphans)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Nettoie les photos orphelines (fichiers manquants)"
    )
    parser.add_argument(
        '--delete',
        action='store_true',
        help="Supprime les enregistrements orphelins (sans cette option, mode dry-run)"
    )

    args = parser.parse_args()

    print("\n🔍 Recherche des photos orphelines...")
    print(f"   MEDIA_ROOT: {settings.MEDIA_ROOT}\n")

    cleanup_orphan_photos(dry_run=not args.delete)


if __name__ == '__main__':
    main()
