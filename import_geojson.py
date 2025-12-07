"""
Script d'importation des données GeoJSON dans la base de données GreenSIG
Usage: python import_geojson.py
"""

import os
import sys
import json
import django
from pathlib import Path

# Configuration Django
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'greensig_web.settings')
django.setup()

from django.contrib.gis.geos import GEOSGeometry, Point, Polygon
from api.models import Site, SousSite, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee

# Mapping des fichiers vers les modèles Django
FILE_TO_MODEL = {
    'arbres.geojson': Arbre,
    'gazon.geojson': Gazon,
    'plamier.geojson': Palmier,  # Note: fichier avec typo "plamier"
    'arbustes.geojson': Arbuste,
    'vivaces.geojson': Vivace,
    'cactus.geojson': Cactus,
    'graminées.geojson': Graminee,
}

# Mapping description -> taille pour les modèles qui ont un champ taille
# (Arbre, Palmier)
TAILLE_MAPPING = {
    'petite': 'Petit',
    'moyenne': 'Moyen',
    'grande': 'Grand',
    'petit': 'Petit',
    'moyen': 'Moyen',
    'grand': 'Grand',
}


def create_default_site():
    """Crée un site par défaut si aucun n'existe"""
    site, created = Site.objects.get_or_create(
        code_site='DEFAULT',
        defaults={
            'nom_site': 'Site par défaut',
            'adresse': 'Importé depuis GeoJSON',
            'actif': True,
            # Créer un polygone par défaut autour du Maroc
            'geometrie_emprise': Polygon.from_bbox((-8.0, 32.0, -7.8, 32.3)),
            'centroid': Point(-7.9, 32.15, srid=4326)
        }
    )
    if created:
        print(f"✓ Site par défaut créé : {site.nom_site}")
    else:
        print(f"✓ Site par défaut existe déjà : {site.nom_site}")
    return site


def normalize_taille(description_value):
    """
    Normalise la valeur de taille depuis le champ description
    Gère les variations de casse et retourne une valeur valide
    """
    if not description_value:
        return 'Moyen'

    desc_lower = str(description_value).lower().strip()
    return TAILLE_MAPPING.get(desc_lower, 'Moyen')


def parse_densite(description_value):
    """
    Essaie de parser une valeur de densité depuis le champ description
    Retourne None si impossible
    """
    if not description_value:
        return None

    try:
        # Essayer de convertir en float
        return float(description_value)
    except (ValueError, TypeError):
        # Si c'est du texte (faible, moyenne, forte), mapper à des valeurs
        desc_lower = str(description_value).lower().strip()
        density_map = {
            'faible': 1.0,
            'moyenne': 2.0,
            'forte': 3.0,
            'low': 1.0,
            'medium': 2.0,
            'high': 3.0,
        }
        return density_map.get(desc_lower, None)


def import_geojson_file(filepath, model_class, site):
    """
    Importe un fichier GeoJSON dans le modèle spécifié

    Args:
        filepath: Chemin vers le fichier GeoJSON
        model_class: Classe du modèle Django (Arbre, Gazon, etc.)
        site: Instance du Site à associer
    """
    filename = os.path.basename(filepath)
    print(f"\n{'='*60}")
    print(f"Import de {filename} vers {model_class.__name__}")
    print(f"{'='*60}")

    if not os.path.exists(filepath):
        print(f"✗ Fichier introuvable : {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        geojson_data = json.load(f)

    features = geojson_data.get('features', [])
    imported_count = 0
    error_count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            properties = feature.get('properties', {})

            # Extraire les propriétés du GeoJSON
            nom_espece = properties.get('nom_espece', 'Espèce inconnue')
            famille = properties.get('famille', '')
            description = properties.get('description', '')

            # Créer la géométrie GEOS
            geom = GEOSGeometry(json.dumps(geometry), srid=4326)

            # Préparer les données communes à tous les objets
            obj_data = {
                'site': site,
                'nom': nom_espece,  # nom_espece -> nom
                'famille': famille,
                'observation': f"Catégorie: {properties.get('categorie', 'N/A')}",
                'geometry': geom
            }

            # Ajouter les champs spécifiques selon le modèle
            if model_class in [Arbre, Palmier]:
                # Pour Arbre et Palmier : description -> taille
                obj_data['taille'] = normalize_taille(description)
                obj_data['symbole'] = ''

            elif model_class == Gazon:
                # Pour Gazon : calculer la surface si possible
                if geometry['type'] == 'Polygon':
                    # Note: area() retourne en degrés carrés, pas en m²
                    # Pour une vraie surface, il faudrait projeter dans un système métrique
                    obj_data['area_sqm'] = None
                else:
                    print(f"  ⚠️  Feature #{idx} : Gazon avec géométrie {geometry['type']} au lieu de Polygon")

            elif model_class in [Arbuste, Vivace, Cactus, Graminee]:
                # Pour ces types : description -> densite
                # Géométrie attendue : Polygon
                if geometry['type'] != 'Polygon':
                    print(f"  ⚠️  Feature #{idx} : {model_class.__name__} avec géométrie {geometry['type']} au lieu de Polygon")

                obj_data['densite'] = parse_densite(description)

                if model_class in [Arbuste, Graminee]:
                    obj_data['symbole'] = ''

            # Créer l'objet
            obj = model_class.objects.create(**obj_data)
            imported_count += 1

            if imported_count % 10 == 0:
                print(f"  Importé {imported_count}/{len(features)} features...")

        except Exception as e:
            error_count += 1
            print(f"✗ Erreur feature #{idx}: {str(e)}")
            if error_count <= 3:  # Afficher les détails pour les 3 premières erreurs
                print(f"  Properties: {properties}")
                print(f"  Geometry type: {geometry.get('type', 'unknown')}")

    print(f"\n✓ Import terminé : {imported_count} objets créés")
    if error_count > 0:
        print(f"✗ Erreurs rencontrées : {error_count}")

    return imported_count


def main():
    """Fonction principale d'import"""
    print("\n" + "="*60)
    print("IMPORT DES DONNÉES GEOJSON - GreenSIG")
    print("="*60)

    # Créer le site par défaut
    site = create_default_site()

    # Dossier contenant les GeoJSON
    geojson_dir = BASE_DIR / 'geojson_vegetation'

    if not geojson_dir.exists():
        print(f"\n✗ Erreur : Le dossier {geojson_dir} n'existe pas")
        return

    # Statistiques globales
    total_imported = 0

    # Importer chaque fichier
    for filename, model_class in FILE_TO_MODEL.items():
        filepath = geojson_dir / filename
        count = import_geojson_file(filepath, model_class, site)
        total_imported += count

    # Résumé final
    print("\n" + "="*60)
    print("RÉSUMÉ DE L'IMPORT")
    print("="*60)
    print(f"Total d'objets importés : {total_imported}")
    print(f"\nDétail par type :")
    print(f"  - Arbres      : {Arbre.objects.count()}")
    print(f"  - Gazons      : {Gazon.objects.count()}")
    print(f"  - Palmiers    : {Palmier.objects.count()}")
    print(f"  - Arbustes    : {Arbuste.objects.count()}")
    print(f"  - Vivaces     : {Vivace.objects.count()}")
    print(f"  - Cactus      : {Cactus.objects.count()}")
    print(f"  - Graminées   : {Graminee.objects.count()}")
    print("="*60 + "\n")


if __name__ == '__main__':
    # Demander confirmation
    print("\n⚠️  ATTENTION : Ce script va importer des données dans votre base.")
    response = input("Continuer ? (o/n) : ")

    if response.lower() in ['o', 'oui', 'y', 'yes']:
        main()
    else:
        print("Import annulé.")
