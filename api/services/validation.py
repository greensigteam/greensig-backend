# api/services/validation.py
"""
Service de validation topologique et opérations géométriques pour GreenSIG.
Utilise GEOS via Django pour les opérations spatiales avancées.
"""

from typing import Dict, List, Any, Optional, Tuple
from django.contrib.gis.geos import (
    GEOSGeometry, Point, LineString, Polygon,
    MultiPoint, MultiLineString, MultiPolygon,
    GeometryCollection
)
from django.contrib.gis.measure import Area, Distance
from django.contrib.gis.db.models.functions import Distance as DistanceFunc
from django.db.models import Q
import json
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# VALIDATION TOPOLOGIQUE
# =============================================================================

def validate_geometry(geometry: GEOSGeometry) -> Dict[str, Any]:
    """
    Valide une géométrie et retourne un rapport détaillé.

    Args:
        geometry: Géométrie GEOS à valider

    Returns:
        Dict avec is_valid, errors, warnings, suggestions
    """
    result = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'suggestions': [],
        'geometry_type': geometry.geom_type,
        'num_coords': geometry.num_coords,
        'num_geoms': geometry.num_geom if hasattr(geometry, 'num_geom') else 1,
    }

    # Vérification de base
    if not geometry.valid:
        result['is_valid'] = False
        result['errors'].append({
            'code': 'INVALID_GEOMETRY',
            'message': f'Géométrie invalide: {geometry.valid_reason}',
            'reason': geometry.valid_reason
        })

    # Vérification géométrie vide
    if geometry.empty:
        result['is_valid'] = False
        result['errors'].append({
            'code': 'EMPTY_GEOMETRY',
            'message': 'La géométrie est vide'
        })
        return result

    # Vérifications spécifiques par type
    if geometry.geom_type == 'Polygon':
        result = _validate_polygon(geometry, result)
    elif geometry.geom_type == 'MultiPolygon':
        for i, poly in enumerate(geometry):
            sub_result = _validate_polygon(poly, {'errors': [], 'warnings': [], 'suggestions': []})
            for error in sub_result['errors']:
                error['polygon_index'] = i
                result['errors'].append(error)
            for warning in sub_result['warnings']:
                warning['polygon_index'] = i
                result['warnings'].append(warning)
        if result['errors']:
            result['is_valid'] = False
    elif geometry.geom_type == 'LineString':
        result = _validate_linestring(geometry, result)
    elif geometry.geom_type == 'MultiLineString':
        for i, line in enumerate(geometry):
            sub_result = _validate_linestring(line, {'errors': [], 'warnings': [], 'suggestions': []})
            for error in sub_result['errors']:
                error['line_index'] = i
                result['errors'].append(error)
            for warning in sub_result['warnings']:
                warning['line_index'] = i
                result['warnings'].append(warning)
        if result['errors']:
            result['is_valid'] = False
    elif geometry.geom_type == 'Point':
        result = _validate_point(geometry, result)

    return result


def _validate_polygon(polygon: Polygon, result: Dict) -> Dict:
    """Validations spécifiques aux polygones."""

    # Vérifier l'aire
    area = polygon.area
    if area < 1e-10:
        result['warnings'].append({
            'code': 'TINY_AREA',
            'message': 'Polygone avec une aire très petite',
            'area': area
        })

    # Vérifier auto-intersection
    if not polygon.simple:
        result['is_valid'] = False
        result['errors'].append({
            'code': 'SELF_INTERSECTION',
            'message': 'Le polygone présente des auto-intersections'
        })

    # Vérifier l'orientation du ring extérieur (doit être anti-horaire en GeoJSON)
    exterior_ring = polygon.exterior_ring
    if exterior_ring and len(exterior_ring) >= 4:
        # Calcul de l'aire signée pour détecter l'orientation
        signed_area = 0
        coords = list(exterior_ring.coords)
        for i in range(len(coords) - 1):
            signed_area += (coords[i+1][0] - coords[i][0]) * (coords[i+1][1] + coords[i][1])

        if signed_area > 0:  # Horaire = positif
            result['warnings'].append({
                'code': 'CLOCKWISE_EXTERIOR',
                'message': 'Le ring extérieur est orienté dans le sens horaire (convention GeoJSON: anti-horaire)'
            })

    # Vérifier les trous
    num_holes = polygon.num_interior_rings
    if num_holes > 0:
        result['warnings'].append({
            'code': 'HAS_HOLES',
            'message': f'Le polygone contient {num_holes} trou(s)',
            'num_holes': num_holes
        })

        # Vérifier que les trous sont à l'intérieur
        for i in range(num_holes):
            hole = polygon.get_interior_ring(i)
            hole_polygon = Polygon(hole)
            if not polygon.contains(hole_polygon):
                result['errors'].append({
                    'code': 'HOLE_OUTSIDE',
                    'message': f'Le trou {i} dépasse du polygone extérieur',
                    'hole_index': i
                })
                result['is_valid'] = False

    # Vérifier les sommets dupliqués consécutifs
    coords = list(exterior_ring.coords)
    for i in range(len(coords) - 2):  # -2 car le dernier = premier
        if coords[i] == coords[i+1]:
            result['warnings'].append({
                'code': 'DUPLICATE_VERTEX',
                'message': f'Sommet dupliqué à l\'index {i}',
                'index': i,
                'coordinate': coords[i]
            })

    return result


def _validate_linestring(line: LineString, result: Dict) -> Dict:
    """Validations spécifiques aux lignes."""

    # Vérifier la longueur
    length = line.length
    if length < 1e-10:
        result['warnings'].append({
            'code': 'TINY_LENGTH',
            'message': 'Ligne avec une longueur très petite',
            'length': length
        })

    # Vérifier nombre de points minimum
    if line.num_points < 2:
        result['is_valid'] = False
        result['errors'].append({
            'code': 'INSUFFICIENT_POINTS',
            'message': 'Une ligne doit avoir au moins 2 points',
            'num_points': line.num_points
        })

    # Vérifier auto-intersection
    if not line.simple:
        result['warnings'].append({
            'code': 'SELF_INTERSECTION',
            'message': 'La ligne présente des auto-intersections'
        })

    return result


def _validate_point(point: Point, result: Dict) -> Dict:
    """Validations spécifiques aux points."""

    # Vérifier coordonnées valides (WGS84)
    lon, lat = point.x, point.y

    if not (-180 <= lon <= 180):
        result['is_valid'] = False
        result['errors'].append({
            'code': 'INVALID_LONGITUDE',
            'message': f'Longitude hors limites: {lon}',
            'value': lon
        })

    if not (-90 <= lat <= 90):
        result['is_valid'] = False
        result['errors'].append({
            'code': 'INVALID_LATITUDE',
            'message': f'Latitude hors limites: {lat}',
            'value': lat
        })

    return result


# =============================================================================
# DÉTECTION DE DOUBLONS
# =============================================================================

def detect_duplicates(
    geometry: GEOSGeometry,
    model_class,
    site_id: Optional[int] = None,
    tolerance: float = 0.0001,
    exclude_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Détecte les doublons potentiels dans la base de données.

    Args:
        geometry: Géométrie à vérifier
        model_class: Classe du modèle Django
        site_id: Filtrer par site (optionnel)
        tolerance: Distance de tolérance en degrés (~11m à l'équateur pour 0.0001)
        exclude_id: ID à exclure de la recherche

    Returns:
        Liste des doublons potentiels avec distance
    """
    duplicates = []

    # Construire le filtre
    queryset = model_class.objects.all()

    if site_id:
        queryset = queryset.filter(site_id=site_id)

    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)

    # Déterminer le champ géométrique
    geo_field = None
    for field in model_class._meta.get_fields():
        if hasattr(field, 'geom_type'):
            geo_field = field.name
            break

    if not geo_field:
        return duplicates

    # Recherche par distance
    buffer = geometry.buffer(tolerance)

    # Filtrer par intersection avec le buffer
    filter_kwargs = {f'{geo_field}__intersects': buffer}
    nearby = queryset.filter(**filter_kwargs)

    for obj in nearby[:20]:  # Limiter à 20 résultats
        obj_geom = getattr(obj, geo_field)
        if obj_geom:
            # Calculer la distance
            if geometry.geom_type == 'Point' and obj_geom.geom_type == 'Point':
                distance = geometry.distance(obj_geom)
            else:
                distance = geometry.centroid.distance(obj_geom.centroid)

            duplicates.append({
                'id': obj.pk,
                'type': obj.__class__.__name__,
                'nom': getattr(obj, 'nom', str(obj)),
                'distance_degrees': distance,
                'distance_meters': distance * 111000,  # Approximation
                'is_exact': distance < 1e-8,
            })

    # Trier par distance
    duplicates.sort(key=lambda x: x['distance_degrees'])

    return duplicates


def find_existing_match(
    geometry: GEOSGeometry,
    model_class,
    site_id: Optional[int],
    target_type: str,
    mapped_properties: Dict[str, Any],
    tolerance_meters: float = 5.0
) -> Optional[Dict[str, Any]]:
    """
    Find an existing object that matches by name/marque + site + proximity.

    Strategy per type:
    - Types with 'nom' (Arbre, Palmier, Gazon, Arbuste, Vivace, Cactus, Graminee, Puit, Pompe):
      site + nom (iexact) + geometry <5m
    - Types with 'marque' without nom (Vanne, Clapet, Ballon, Canalisation, Aspersion):
      site + marque (iexact) + geometry <5m
    - Goutte (neither nom nor marque): site + geometry <5m only
    - Site: match by code_site (unique field)

    Returns:
        None if no match, else {'id': int, 'nom': str, 'match_type': str}
    """
    from django.contrib.gis.measure import D

    if target_type == 'Site':
        code = mapped_properties.get('code_site')
        if code:
            try:
                obj = model_class.objects.get(code_site__iexact=code)
                return {
                    'id': obj.pk,
                    'nom': getattr(obj, 'nom_site', str(obj)),
                    'match_type': 'code_site',
                }
            except model_class.DoesNotExist:
                return None
        # Fallback: match by geometry intersection
        obj = model_class.objects.filter(
            geometrie_emprise__intersects=geometry
        ).first()
        if obj:
            return {
                'id': obj.pk,
                'nom': getattr(obj, 'nom_site', str(obj)),
                'match_type': 'geo_intersects',
            }
        return None

    # Build base queryset filtered by site
    queryset = model_class.objects.all()
    if site_id:
        queryset = queryset.filter(site_id=site_id)

    # Filter by proximity
    queryset = queryset.filter(geometry__distance_lte=(geometry, D(m=tolerance_meters)))

    # Types with 'nom' field
    types_with_nom = {'Arbre', 'Palmier', 'Gazon', 'Arbuste', 'Vivace', 'Cactus', 'Graminee', 'Puit', 'Pompe'}
    # Types with 'marque' field (no nom)
    types_with_marque = {'Vanne', 'Clapet', 'Ballon', 'Canalisation', 'Aspersion'}

    if target_type in types_with_nom:
        nom = mapped_properties.get('nom')
        if nom:
            queryset = queryset.filter(nom__iexact=nom)
            match_type = 'nom+site+geo'
        else:
            # No nom mapped — fallback to site + proximity only
            match_type = 'site+geo'
    elif target_type in types_with_marque:
        marque = mapped_properties.get('marque')
        if marque:
            queryset = queryset.filter(marque__iexact=marque)
            match_type = 'marque+site+geo'
        else:
            # No marque mapped — fallback to site + proximity only
            match_type = 'site+geo'
    else:
        # Goutte: geometry + site only
        match_type = 'site+geo'

    obj = queryset.first()
    if obj:
        display_name = getattr(obj, 'nom', None) or getattr(obj, 'marque', None) or str(obj)
        return {
            'id': obj.pk,
            'nom': display_name,
            'match_type': match_type,
        }

    return None


# =============================================================================
# VÉRIFICATION HORS EMPRISE
# =============================================================================

def check_within_site(
    geometry: GEOSGeometry,
    site_id: int
) -> Dict[str, Any]:
    """
    Vérifie si une géométrie est bien à l'intérieur de l'emprise du site.

    Args:
        geometry: Géométrie à vérifier
        site_id: ID du site

    Returns:
        Dict avec is_within, percentage_inside, warnings
    """
    from api.models import Site

    result = {
        'is_within': True,
        'percentage_inside': 100.0,
        'warnings': [],
        'site_id': site_id
    }

    try:
        site = Site.objects.get(pk=site_id)
    except Site.DoesNotExist:
        result['is_within'] = False
        result['warnings'].append({
            'code': 'SITE_NOT_FOUND',
            'message': f'Site {site_id} introuvable'
        })
        return result

    site_boundary = site.geometrie_emprise
    if not site_boundary:
        result['warnings'].append({
            'code': 'NO_SITE_BOUNDARY',
            'message': 'Le site n\'a pas d\'emprise définie'
        })
        return result

    # Vérifier si complètement à l'intérieur
    if site_boundary.contains(geometry):
        return result

    # Calculer le pourcentage à l'intérieur
    try:
        intersection = geometry.intersection(site_boundary)
        if geometry.area > 0:
            percentage = (intersection.area / geometry.area) * 100
        elif geometry.length > 0:
            percentage = (intersection.length / geometry.length) * 100
        else:
            # Point
            percentage = 100.0 if site_boundary.contains(geometry) else 0.0

        result['percentage_inside'] = round(percentage, 2)

        if percentage < 100:
            result['is_within'] = False
            result['warnings'].append({
                'code': 'OUTSIDE_BOUNDARY',
                'message': f'{100 - percentage:.1f}% de l\'objet est hors de l\'emprise du site',
                'percentage_outside': round(100 - percentage, 2)
            })

        if percentage == 0:
            result['warnings'].append({
                'code': 'COMPLETELY_OUTSIDE',
                'message': 'L\'objet est entièrement hors de l\'emprise du site'
            })

    except Exception as e:
        logger.warning(f"Erreur calcul intersection: {e}")
        result['is_within'] = False
        result['warnings'].append({
            'code': 'CALCULATION_ERROR',
            'message': str(e)
        })

    return result


# =============================================================================
# OPÉRATIONS GÉOMÉTRIQUES
# =============================================================================

def simplify_geometry(
    geometry: GEOSGeometry,
    tolerance: float = 0.0001,
    preserve_topology: bool = True
) -> Tuple[GEOSGeometry, Dict[str, Any]]:
    """
    Simplifie une géométrie en réduisant le nombre de sommets.

    Args:
        geometry: Géométrie à simplifier
        tolerance: Tolérance de simplification (en degrés)
        preserve_topology: Préserver la topologie (évite auto-intersections)

    Returns:
        Tuple (géométrie simplifiée, statistiques)
    """
    original_coords = geometry.num_coords

    if preserve_topology:
        simplified = geometry.simplify(tolerance, preserve_topology=True)
    else:
        simplified = geometry.simplify(tolerance, preserve_topology=False)

    stats = {
        'original_coords': original_coords,
        'simplified_coords': simplified.num_coords,
        'reduction_percent': round((1 - simplified.num_coords / original_coords) * 100, 2) if original_coords > 0 else 0,
        'tolerance_used': tolerance,
        'topology_preserved': preserve_topology,
        'is_valid': simplified.valid
    }

    return simplified, stats


def split_polygon(
    polygon: GEOSGeometry,
    split_line: LineString
) -> Tuple[List[GEOSGeometry], Dict[str, Any]]:
    """
    Divise un polygone avec une ligne de coupe.

    Args:
        polygon: Polygone à diviser
        split_line: Ligne de coupe

    Returns:
        Tuple (liste des polygones résultants, statistiques)
    """
    result_polygons = []
    stats = {
        'success': False,
        'num_parts': 0,
        'errors': []
    }

    # Vérifier que c'est bien un polygone
    if polygon.geom_type not in ('Polygon', 'MultiPolygon'):
        stats['errors'].append('La géométrie doit être un Polygon ou MultiPolygon')
        return result_polygons, stats

    # Vérifier que la ligne traverse le polygone
    if not split_line.intersects(polygon):
        stats['errors'].append('La ligne de coupe ne traverse pas le polygone')
        return result_polygons, stats

    try:
        # Utiliser la différence symétrique avec un buffer très fin de la ligne
        # pour créer la division
        line_buffer = split_line.buffer(1e-9)

        # Méthode alternative: utiliser la ligne comme boundary
        # et faire une opération de split via GEOS
        from django.contrib.gis.geos import GEOSGeometry

        # Calculer la différence
        result = polygon.difference(line_buffer)

        if result.geom_type == 'Polygon':
            result_polygons = [result]
        elif result.geom_type == 'MultiPolygon':
            result_polygons = list(result)
        elif result.geom_type == 'GeometryCollection':
            result_polygons = [g for g in result if g.geom_type in ('Polygon', 'MultiPolygon')]

        # Filtrer les polygones trop petits (artefacts)
        min_area = polygon.area * 0.001  # 0.1% de l'aire originale
        result_polygons = [p for p in result_polygons if p.area > min_area]

        stats['success'] = len(result_polygons) > 1
        stats['num_parts'] = len(result_polygons)
        stats['areas'] = [p.area for p in result_polygons]

    except Exception as e:
        stats['errors'].append(str(e))
        logger.error(f"Erreur split_polygon: {e}")

    return result_polygons, stats


def merge_polygons(
    polygons: List[GEOSGeometry]
) -> Tuple[Optional[GEOSGeometry], Dict[str, Any]]:
    """
    Fusionne plusieurs polygones en un seul.

    Args:
        polygons: Liste des polygones à fusionner

    Returns:
        Tuple (polygone fusionné ou None, statistiques)
    """
    stats = {
        'success': False,
        'input_count': len(polygons),
        'output_type': None,
        'total_area_before': 0,
        'total_area_after': 0,
        'errors': []
    }

    if len(polygons) < 2:
        stats['errors'].append('Au moins 2 polygones sont nécessaires pour une fusion')
        return None, stats

    # Calculer l'aire totale avant
    stats['total_area_before'] = sum(p.area for p in polygons)

    try:
        # Union successive
        result = polygons[0]
        for poly in polygons[1:]:
            result = result.union(poly)

        stats['success'] = True
        stats['output_type'] = result.geom_type
        stats['total_area_after'] = result.area
        stats['is_valid'] = result.valid

        # Vérifier si le résultat est un MultiPolygon (polygones non adjacents)
        if result.geom_type == 'MultiPolygon':
            stats['warnings'] = ['Les polygones ne sont pas tous adjacents, résultat en MultiPolygon']
            stats['num_parts'] = result.num_geom

        return result, stats

    except Exception as e:
        stats['errors'].append(str(e))
        logger.error(f"Erreur merge_polygons: {e}")
        return None, stats


def calculate_geometry_metrics(geometry: GEOSGeometry) -> Dict[str, Any]:
    """
    Calcule les métriques d'une géométrie (aire, longueur, périmètre, centroïde).

    Args:
        geometry: Géométrie à analyser

    Returns:
        Dict avec toutes les métriques calculées
    """
    metrics = {
        'geometry_type': geometry.geom_type,
        'srid': geometry.srid,
        'num_coords': geometry.num_coords,
        'is_valid': geometry.valid,
    }

    # Centroïde
    centroid = geometry.centroid
    metrics['centroid'] = {
        'lng': centroid.x,
        'lat': centroid.y
    }

    # Bounding box
    extent = geometry.extent  # (xmin, ymin, xmax, ymax)
    metrics['bbox'] = {
        'min_lng': extent[0],
        'min_lat': extent[1],
        'max_lng': extent[2],
        'max_lat': extent[3]
    }

    # Métriques selon le type
    if geometry.geom_type in ('Polygon', 'MultiPolygon'):
        # Aire en degrés carrés
        area_deg = geometry.area
        metrics['area_degrees_sq'] = area_deg

        # Conversion approximative en m² (à l'équateur)
        # 1 degré = ~111km, donc 1 deg² = ~12321 km² = ~12321000000 m²
        # Mais c'est très approximatif, mieux vaut utiliser une projection
        lat = centroid.y
        import math
        cos_lat = math.cos(math.radians(lat))
        area_m2 = area_deg * (111000 ** 2) * cos_lat
        metrics['area_m2'] = round(area_m2, 2)
        metrics['area_hectares'] = round(area_m2 / 10000, 4)

        # Périmètre
        if geometry.geom_type == 'Polygon':
            perimeter_deg = geometry.exterior_ring.length
        else:
            perimeter_deg = sum(p.exterior_ring.length for p in geometry)

        perimeter_m = perimeter_deg * 111000 * cos_lat
        metrics['perimeter_m'] = round(perimeter_m, 2)

    elif geometry.geom_type in ('LineString', 'MultiLineString'):
        length_deg = geometry.length
        metrics['length_degrees'] = length_deg

        # Conversion approximative
        lat = centroid.y
        import math
        cos_lat = math.cos(math.radians(lat))
        length_m = length_deg * 111000 * cos_lat
        metrics['length_m'] = round(length_m, 2)
        metrics['length_km'] = round(length_m / 1000, 4)

    elif geometry.geom_type in ('Point', 'MultiPoint'):
        metrics['coordinates'] = {
            'lng': geometry.x if geometry.geom_type == 'Point' else [p.x for p in geometry],
            'lat': geometry.y if geometry.geom_type == 'Point' else [p.y for p in geometry]
        }
        if geometry.geom_type == 'MultiPoint':
            metrics['num_points'] = geometry.num_geom

    return metrics


def buffer_geometry(
    geometry: GEOSGeometry,
    distance_meters: float,
    quad_segs: int = 8
) -> Tuple[GEOSGeometry, Dict[str, Any]]:
    """
    Crée un buffer autour d'une géométrie.

    Args:
        geometry: Géométrie source
        distance_meters: Distance du buffer en mètres
        quad_segs: Nombre de segments pour approximer les courbes

    Returns:
        Tuple (géométrie bufferisée, statistiques)
    """
    # Conversion mètres -> degrés (approximation)
    lat = geometry.centroid.y
    import math
    cos_lat = math.cos(math.radians(lat))
    distance_deg = distance_meters / (111000 * cos_lat)

    buffered = geometry.buffer(distance_deg, quadsegs=quad_segs)

    stats = {
        'input_type': geometry.geom_type,
        'output_type': buffered.geom_type,
        'distance_meters': distance_meters,
        'distance_degrees': distance_deg,
        'area_increase': buffered.area - geometry.area if geometry.geom_type in ('Polygon', 'MultiPolygon') else buffered.area
    }

    return buffered, stats
