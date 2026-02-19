"""
Commande Django : Met à jour le champ 'taille' des Arbres et Palmiers existants
en se basant sur les coordonnées du GeoJSON original.

Usage:
    python manage.py patch_taille
    python manage.py patch_taille --geojson-dir /chemin/vers/geojson
    docker compose exec backend python manage.py patch_taille
"""
import json
import os

from django.core.management.base import BaseCommand
from django.contrib.gis.geos import Point
from django.contrib.gis.measure import D

from api.models import Arbre, Palmier


TAILLE_MAPPING = {
    'petite': 'Petit',
    'moyenne': 'Moyen',
    'grande': 'Grand',
    'petit': 'Petit',
    'moyen': 'Moyen',
    'grand': 'Grand',
}

DEFAULT_GEOJSON_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'GeoJSON', 'GeoJSON')

FILES = [
    ('arbres.GeoJSON', Arbre),
    ('palmier.GeoJSON', Palmier),
]


class Command(BaseCommand):
    help = "Met à jour le champ 'taille' des Arbres et Palmiers depuis les fichiers GeoJSON"

    def add_arguments(self, parser):
        parser.add_argument(
            '--geojson-dir',
            type=str,
            default=DEFAULT_GEOJSON_DIR,
            help='Chemin vers le dossier contenant les fichiers GeoJSON',
        )

    def handle(self, *args, **options):
        geojson_dir = options['geojson_dir']
        self.stdout.write(f"Dossier GeoJSON : {geojson_dir}")

        total_updated = 0
        total_not_found = 0
        total_skipped = 0

        for filename, Model in FILES:
            filepath = os.path.join(geojson_dir, filename)
            if not os.path.exists(filepath):
                self.stdout.write(self.style.WARNING(f"SKIP: {filepath} introuvable"))
                continue

            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            features = data.get('features', [])
            model_name = Model.__name__
            updated = 0
            not_found = 0
            skipped = 0

            for feat in features:
                props = feat.get('properties', {})
                descriptio = props.get('descriptio')
                if not descriptio:
                    skipped += 1
                    continue

                taille = TAILLE_MAPPING.get(descriptio.lower().strip())
                if not taille:
                    skipped += 1
                    continue

                coords = feat['geometry']['coordinates']
                point = Point(coords[0], coords[1], srid=4326)

                matches = Model.objects.filter(
                    geometry__distance_lte=(point, D(m=0.5))
                )

                if matches.exists():
                    count = matches.filter(taille__isnull=True).update(taille=taille)
                    count += matches.filter(taille='').update(taille=taille)
                    if count > 0:
                        updated += count
                    else:
                        skipped += 1
                else:
                    not_found += 1

            self.stdout.write(f"{model_name}: {updated} mis à jour, {not_found} non trouvés, {skipped} ignorés")
            total_updated += updated
            total_not_found += not_found
            total_skipped += skipped

        self.stdout.write(self.style.SUCCESS(
            f"\nTotal: {total_updated} mis à jour, {total_not_found} non trouvés, {total_skipped} ignorés"
        ))
