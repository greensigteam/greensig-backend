"""
Script d'importation des données GeoJSON v2 - GreenSIG
Importe Sites, Végétation et Hydraulique depuis les fichiers GeoJSON.

Usage: python import_geojson_v2.py
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

from django.contrib.gis.geos import GEOSGeometry, Point, Polygon, LineString, MultiPolygon, MultiLineString
from api.models import (
    Site, SousSite,
    Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)

# Chemin vers le dossier GeoJSON
GEOJSON_DIR = Path(__file__).resolve().parent.parent / 'GreenSIGfull' / 'GeoJSON'

# Mapping taille
TAILLE_MAPPING = {
    'petite': 'Petit',
    'moyenne': 'Moyen',
    'grande': 'Grand',
    'petit': 'Petit',
    'moyen': 'Moyen',
    'grand': 'Grand',
}


def normalize_taille(value):
    """Normalise la valeur de taille"""
    if not value:
        return 'Moyen'
    return TAILLE_MAPPING.get(str(value).lower().strip(), 'Moyen')


def parse_float(value):
    """Parse une valeur en float, gère les virgules et valeurs vides"""
    if value is None or value == '':
        return None
    try:
        # Remplacer virgule par point pour les décimaux
        return float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        return None


def parse_densite(value):
    """Parse une valeur de densité"""
    if value is None or value == '':
        return None

    # Si c'est déjà un nombre
    try:
        return float(value)
    except (ValueError, TypeError):
        pass

    # Mapping texte vers valeur
    density_map = {
        'faible': 1.0,
        'moyenne': 2.0,
        'forte': 3.0,
        'dense': 3.0,
    }
    return density_map.get(str(value).lower().strip(), None)


def convert_geometry(geom_dict, target_type):
    """
    Convertit une géométrie GeoJSON vers le type cible.
    Gère les Multi* vers types simples si nécessaire.
    """
    geom = GEOSGeometry(json.dumps(geom_dict), srid=4326)
    geom_type = geom_dict.get('type', '')

    # MultiPolygon -> Polygon (prendre le premier)
    if target_type == 'Polygon' and geom_type == 'MultiPolygon':
        if isinstance(geom, MultiPolygon) and len(geom) > 0:
            return geom[0]

    # MultiLineString -> LineString (prendre le premier ou fusionner)
    if target_type == 'LineString' and geom_type == 'MultiLineString':
        if isinstance(geom, MultiLineString) and len(geom) > 0:
            # Fusionner tous les segments en une seule ligne
            all_coords = []
            for line in geom:
                all_coords.extend(list(line.coords))
            return LineString(all_coords, srid=4326)

    return geom


# ==============================================================================
# IMPORT DES SITES
# ==============================================================================

def import_sites():
    """Importe les sites depuis Sites.GeoJSON"""
    filepath = GEOJSON_DIR / 'Sites.GeoJSON'
    print(f"\n{'='*60}")
    print(f"Import des SITES depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return []

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    sites_created = []

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            # Créer la géométrie
            geom = convert_geometry(geometry, 'Polygon')

            # Calculer le centroid pour le nom
            centroid = geom.centroid

            # Générer un nom basé sur les coordonnées
            nom_site = f"Site {idx} ({centroid.y:.4f}, {centroid.x:.4f})"
            code_site = f"SITE_{idx:03d}"

            # Créer le site
            site = Site.objects.create(
                nom_site=nom_site,
                code_site=code_site,
                adresse=f"Coordonnées: {centroid.y:.6f}, {centroid.x:.6f}",
                geometrie_emprise=geom,
                centroid=centroid,
                actif=True
            )
            sites_created.append(site)
            print(f"  + Site créé: {nom_site}")

        except Exception as e:
            print(f"  ! Erreur site #{idx}: {e}")

    print(f"\n  Total sites créés: {len(sites_created)}")
    return sites_created


# ==============================================================================
# IMPORT VEGETATION
# ==============================================================================

def import_arbres(site):
    """Importe les arbres"""
    filepath = GEOJSON_DIR / 'arbres.GeoJSON'
    return import_point_vegetation(filepath, Arbre, site, has_taille=True)


def import_palmiers(site):
    """Importe les palmiers"""
    filepath = GEOJSON_DIR / 'palmier.GeoJSON'
    return import_point_vegetation(filepath, Palmier, site, has_taille=True)


def import_point_vegetation(filepath, model_class, site, has_taille=False):
    """Import générique pour végétation ponctuelle (Arbre, Palmier)"""
    print(f"\n{'='*60}")
    print(f"Import {model_class.__name__} depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            geom = GEOSGeometry(json.dumps(geometry), srid=4326)

            obj_data = {
                'site': site,
                'nom': props.get('nom_espece', f'{model_class.__name__} #{idx}'),
                'famille': props.get('famille', ''),
                'observation': '',
                'geometry': geom
            }

            if has_taille:
                obj_data['taille'] = normalize_taille(props.get('descriptio'))
                obj_data['symbole'] = ''

            model_class.objects.create(**obj_data)
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


def import_gazons(site):
    """Importe les gazons"""
    filepath = GEOJSON_DIR / 'gazon.GeoJSON'
    return import_polygon_vegetation(filepath, Gazon, site, has_area=True)


def import_arbustes(site):
    """Importe les arbustes"""
    filepath = GEOJSON_DIR / 'arbuste.GeoJSON'
    return import_polygon_vegetation(filepath, Arbuste, site, has_densite=True)


def import_vivaces(site):
    """Importe les vivaces"""
    filepath = GEOJSON_DIR / 'Vivaces.GeoJSON'
    return import_polygon_vegetation(filepath, Vivace, site, has_densite=True)


def import_cactus(site):
    """Importe les cactus"""
    filepath = GEOJSON_DIR / 'cactus.GeoJSON'
    return import_polygon_vegetation(filepath, Cactus, site, has_densite=True)


def import_graminees(site):
    """Importe les graminées"""
    filepath = GEOJSON_DIR / 'graminiées.GeoJSON'
    return import_polygon_vegetation(filepath, Graminee, site, has_densite=True)


def import_polygon_vegetation(filepath, model_class, site, has_area=False, has_densite=False):
    """Import générique pour végétation polygonale"""
    print(f"\n{'='*60}")
    print(f"Import {model_class.__name__} depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            # Convertir MultiPolygon en Polygon
            geom = convert_geometry(geometry, 'Polygon')

            obj_data = {
                'site': site,
                'nom': props.get('nom_espece', f'{model_class.__name__} #{idx}'),
                'famille': props.get('famille', ''),
                'observation': '',
                'geometry': geom
            }

            if has_area:
                obj_data['area_sqm'] = None  # À calculer si besoin

            if has_densite:
                # Essayer 'Densité' ou 'descriptio'
                densite = props.get('Densité') or props.get('descriptio')
                obj_data['densite'] = parse_densite(densite)
                if hasattr(model_class, 'symbole'):
                    obj_data['symbole'] = ''

            model_class.objects.create(**obj_data)
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


# ==============================================================================
# IMPORT HYDRAULIQUE
# ==============================================================================

def import_puits(site):
    """Importe les puits"""
    filepath = GEOJSON_DIR / 'Puit.GeoJSON'
    print(f"\n{'='*60}")
    print(f"Import Puit depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            geom = GEOSGeometry(json.dumps(geometry), srid=4326)

            Puit.objects.create(
                site=site,
                nom=props.get('nom_equipe', f'Puit #{idx}'),
                profondeur=parse_float(props.get('profondeur')),
                diametre=parse_float(props.get('diametre')),
                niveau_statique=parse_float(props.get('niveau_sta')),
                niveau_dynamique=parse_float(props.get('niveau_dyn')),
                geometry=geom
            )
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


def import_pompes(site):
    """Importe les pompes"""
    filepath = GEOJSON_DIR / 'Pompe.GeoJSON'
    print(f"\n{'='*60}")
    print(f"Import Pompe depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            geom = GEOSGeometry(json.dumps(geometry), srid=4326)

            Pompe.objects.create(
                site=site,
                nom=props.get('nom_equipe', f'Pompe #{idx}'),
                type=props.get('type', ''),
                diametre=parse_float(props.get('diametre')),
                puissance=parse_float(props.get('puissance')),
                debit=parse_float(props.get('debit')),
                geometry=geom
            )
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


def import_vannes(site):
    """Importe les vannes"""
    filepath = GEOJSON_DIR / 'Vanne.GeoJSON'
    print(f"\n{'='*60}")
    print(f"Import Vanne depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            geom = GEOSGeometry(json.dumps(geometry), srid=4326)

            Vanne.objects.create(
                site=site,
                marque='',
                type=props.get('type_mode', ''),
                diametre=parse_float(props.get('diametre')),
                materiau=props.get('materiau', ''),
                pression=parse_float(props.get('pression_n')),
                geometry=geom
            )
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


def import_ballons(site):
    """Importe les ballons"""
    filepath = GEOJSON_DIR / 'Ballon.GeoJSON'
    print(f"\n{'='*60}")
    print(f"Import Ballon depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            geom = GEOSGeometry(json.dumps(geometry), srid=4326)

            Ballon.objects.create(
                site=site,
                marque=props.get('nom_equipe', f'Ballon #{idx}'),
                pression=parse_float(props.get('pression')),
                volume=parse_float(props.get('volume')),
                geometry=geom
            )
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


def import_canalisations(site):
    """Importe les canalisations"""
    filepath = GEOJSON_DIR / 'Canalisation.GeoJSON'
    print(f"\n{'='*60}")
    print(f"Import Canalisation depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            # Convertir MultiLineString en LineString
            geom = convert_geometry(geometry, 'LineString')

            Canalisation.objects.create(
                site=site,
                marque='',
                type='',
                diametre=parse_float(props.get('diametre')),
                materiau=props.get('materiau', ''),
                pression=parse_float(props.get('pression_n')),
                geometry=geom
            )
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


def import_aspersions(site):
    """Importe les aspersions"""
    filepath = GEOJSON_DIR / 'Aspertion.GeoJSON'  # Note: typo dans le fichier
    print(f"\n{'='*60}")
    print(f"Import Aspersion depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            geom = convert_geometry(geometry, 'LineString')

            Aspersion.objects.create(
                site=site,
                marque='',
                type='',
                geometry=geom
            )
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


def import_gouttes(site):
    """Importe les goutte-à-goutte"""
    filepath = GEOJSON_DIR / 'GaG.GeoJSON'
    print(f"\n{'='*60}")
    print(f"Import Goutte depuis {filepath.name}")
    print(f"{'='*60}")

    if not filepath.exists():
        print(f"  Fichier introuvable: {filepath}")
        return 0

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    count = 0

    for idx, feature in enumerate(features, 1):
        try:
            geometry = feature['geometry']
            props = feature.get('properties', {})

            geom = convert_geometry(geometry, 'LineString')

            Goutte.objects.create(
                site=site,
                type=props.get('descriptio', ''),
                diametre=parse_float(props.get('diametre')),
                materiau=props.get('materiau', ''),
                geometry=geom
            )
            count += 1

        except Exception as e:
            print(f"  ! Erreur #{idx}: {e}")

    print(f"  Total importés: {count}")
    return count


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("\n" + "="*60)
    print("IMPORT DES DONNÉES GEOJSON v2 - GreenSIG")
    print("="*60)
    print(f"\nDossier source: {GEOJSON_DIR}")

    if not GEOJSON_DIR.exists():
        print(f"\n  ERREUR: Le dossier {GEOJSON_DIR} n'existe pas!")
        return

    # 1. Importer les sites
    sites = import_sites()

    # Utiliser le premier site comme site par défaut pour les objets
    if sites:
        default_site = sites[0]
    else:
        # Créer un site par défaut si aucun site n'a été importé
        default_site, _ = Site.objects.get_or_create(
            code_site='DEFAULT',
            defaults={
                'nom_site': 'Site par défaut',
                'geometrie_emprise': Polygon.from_bbox((-8.0, 32.0, -7.8, 32.3)),
                'centroid': Point(-7.9, 32.15, srid=4326),
                'actif': True
            }
        )
        print(f"\n  Site par défaut utilisé: {default_site.nom_site}")

    # 2. Importer la végétation
    total_veg = 0
    total_veg += import_arbres(default_site)
    total_veg += import_palmiers(default_site)
    total_veg += import_gazons(default_site)
    total_veg += import_arbustes(default_site)
    total_veg += import_vivaces(default_site)
    total_veg += import_cactus(default_site)
    total_veg += import_graminees(default_site)

    # 3. Importer l'hydraulique
    total_hydro = 0
    total_hydro += import_puits(default_site)
    total_hydro += import_pompes(default_site)
    total_hydro += import_vannes(default_site)
    total_hydro += import_ballons(default_site)
    total_hydro += import_canalisations(default_site)
    total_hydro += import_aspersions(default_site)
    total_hydro += import_gouttes(default_site)

    # Résumé final
    print("\n" + "="*60)
    print("RÉSUMÉ DE L'IMPORT")
    print("="*60)
    print(f"\nSites importés: {len(sites)}")
    print(f"\nVégétation ({total_veg} objets):")
    print(f"  - Arbres:     {Arbre.objects.count()}")
    print(f"  - Palmiers:   {Palmier.objects.count()}")
    print(f"  - Gazons:     {Gazon.objects.count()}")
    print(f"  - Arbustes:   {Arbuste.objects.count()}")
    print(f"  - Vivaces:    {Vivace.objects.count()}")
    print(f"  - Cactus:     {Cactus.objects.count()}")
    print(f"  - Graminées:  {Graminee.objects.count()}")
    print(f"\nHydraulique ({total_hydro} objets):")
    print(f"  - Puits:         {Puit.objects.count()}")
    print(f"  - Pompes:        {Pompe.objects.count()}")
    print(f"  - Vannes:        {Vanne.objects.count()}")
    print(f"  - Ballons:       {Ballon.objects.count()}")
    print(f"  - Canalisations: {Canalisation.objects.count()}")
    print(f"  - Aspersions:    {Aspersion.objects.count()}")
    print(f"  - Gouttes:       {Goutte.objects.count()}")
    print("\n" + "="*60)


if __name__ == '__main__':
    print("\n  ATTENTION: Ce script va importer des données dans votre base.")
    print("  Assurez-vous d'avoir vidé les anciennes données si nécessaire.")
    response = input("\n  Continuer ? (o/n) : ")

    if response.lower() in ['o', 'oui', 'y', 'yes']:
        main()
    else:
        print("  Import annulé.")
