# api/services/geo_io.py
"""
Service for geo data import/export operations.
Handles GeoJSON, KML, and Shapefile formats.
"""

import json
import zipfile
import tempfile
import os
from io import BytesIO
from typing import List, Dict, Any, Optional, Tuple
from xml.etree import ElementTree as ET

from django.contrib.gis.geos import (
    GEOSGeometry, Point, Polygon, LineString,
    MultiPolygon, MultiLineString, MultiPoint
)

# ==============================================================================
# CONSTANTS
# ==============================================================================

# Mapping object types to their required geometry types
GEOMETRY_TYPE_MAPPING = {
    # Vegetation - Point
    'Arbre': 'Point',
    'Palmier': 'Point',
    # Vegetation - Polygon
    'Gazon': 'Polygon',
    'Arbuste': 'Polygon',
    'Vivace': 'Polygon',
    'Cactus': 'Polygon',
    'Graminee': 'Polygon',
    # Hydraulic - Point
    'Puit': 'Point',
    'Pompe': 'Point',
    'Vanne': 'Point',
    'Clapet': 'Point',
    'Ballon': 'Point',
    # Hydraulic - LineString
    'Canalisation': 'LineString',
    'Aspersion': 'LineString',
    'Goutte': 'LineString',
    # Spatial hierarchy
    'Site': 'Polygon',
    'SousSite': 'Point',
}

# Mapping taille values
TAILLE_MAPPING = {
    'petite': 'Petit',
    'moyenne': 'Moyen',
    'grande': 'Grand',
    'petit': 'Petit',
    'moyen': 'Moyen',
    'grand': 'Grand',
    'small': 'Petit',
    'medium': 'Moyen',
    'large': 'Grand',
}

# Fields per object type
OBJECT_FIELDS = {
    'Arbre': ['nom', 'famille', 'taille', 'symbole', 'observation'],
    'Palmier': ['nom', 'famille', 'taille', 'symbole', 'observation'],
    'Gazon': ['nom', 'famille', 'area_sqm', 'observation'],
    'Arbuste': ['nom', 'famille', 'densite', 'symbole', 'observation'],
    'Vivace': ['nom', 'famille', 'densite', 'observation'],
    'Cactus': ['nom', 'famille', 'densite', 'observation'],
    'Graminee': ['nom', 'famille', 'densite', 'symbole', 'observation'],
    'Puit': ['nom', 'profondeur', 'diametre', 'niveau_statique', 'niveau_dynamique', 'symbole', 'observation'],
    'Pompe': ['nom', 'type', 'diametre', 'puissance', 'debit', 'symbole', 'observation'],
    'Vanne': ['marque', 'type', 'diametre', 'materiau', 'pression', 'symbole', 'observation'],
    'Clapet': ['marque', 'type', 'diametre', 'materiau', 'pression', 'symbole', 'observation'],
    'Ballon': ['marque', 'pression', 'volume', 'materiau', 'observation'],
    'Canalisation': ['marque', 'type', 'diametre', 'materiau', 'pression', 'symbole', 'observation'],
    'Aspersion': ['marque', 'type', 'diametre', 'materiau', 'pression', 'symbole', 'observation'],
    'Goutte': ['type', 'diametre', 'materiau', 'pression', 'symbole', 'observation'],
}


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def normalize_taille(value: Any) -> str:
    """Normalize size value to standard choices."""
    if not value:
        return 'Moyen'
    return TAILLE_MAPPING.get(str(value).lower().strip(), 'Moyen')


def parse_float(value: Any) -> Optional[float]:
    """Parse a value to float, handling commas and empty values."""
    if value is None or value == '':
        return None
    try:
        return float(str(value).replace(',', '.'))
    except (ValueError, TypeError):
        return None


def parse_densite(value: Any) -> Optional[float]:
    """Parse density value from text or number."""
    if value is None or value == '':
        return None

    try:
        return float(value)
    except (ValueError, TypeError):
        pass

    density_map = {
        'faible': 1.0,
        'moyenne': 2.0,
        'forte': 3.0,
        'dense': 3.0,
        'low': 1.0,
        'medium': 2.0,
        'high': 3.0,
    }
    return density_map.get(str(value).lower().strip(), None)


def convert_geometry(geom_dict: Dict, target_type: str) -> GEOSGeometry:
    """
    Convert a GeoJSON geometry to the target type.
    Handles Multi* to simple types conversion.

    Args:
        geom_dict: GeoJSON geometry dict
        target_type: Target geometry type ('Point', 'Polygon', 'LineString')

    Returns:
        GEOSGeometry object
    """
    geom = GEOSGeometry(json.dumps(geom_dict), srid=4326)
    geom_type = geom_dict.get('type', '')

    # MultiPolygon -> Polygon (take first)
    if target_type == 'Polygon' and geom_type == 'MultiPolygon':
        if isinstance(geom, MultiPolygon) and len(geom) > 0:
            return geom[0]

    # MultiLineString -> LineString (merge all segments)
    if target_type == 'LineString' and geom_type == 'MultiLineString':
        if isinstance(geom, MultiLineString) and len(geom) > 0:
            all_coords = []
            for line in geom:
                all_coords.extend(list(line.coords))
            return LineString(all_coords, srid=4326)

    # MultiPoint -> Point (take first)
    if target_type == 'Point' and geom_type == 'MultiPoint':
        if isinstance(geom, MultiPoint) and len(geom) > 0:
            return geom[0]

    # Polygon centroid -> Point
    if target_type == 'Point' and geom_type in ('Polygon', 'MultiPolygon'):
        return geom.centroid

    return geom


def validate_geometry_for_type(geometry: GEOSGeometry, object_type: str) -> Tuple[bool, str]:
    """
    Validate that a geometry is compatible with an object type.

    Args:
        geometry: GEOSGeometry object
        object_type: Target object type ('Arbre', 'Gazon', etc.)

    Returns:
        Tuple of (is_valid, error_message)
    """
    if object_type not in GEOMETRY_TYPE_MAPPING:
        return False, f"Unknown object type: {object_type}"

    expected_type = GEOMETRY_TYPE_MAPPING[object_type]
    actual_type = geometry.geom_type

    # Check direct match
    if actual_type == expected_type:
        return True, ""

    # Check convertible types
    convertible = {
        'Point': ['MultiPoint', 'Polygon', 'MultiPolygon'],  # Can get centroid
        'Polygon': ['MultiPolygon'],
        'LineString': ['MultiLineString'],
    }

    if actual_type in convertible.get(expected_type, []):
        return True, ""

    return False, f"Geometry type {actual_type} not compatible with {object_type} (requires {expected_type})"


def detect_object_type_from_geometry(geometry_type: str) -> List[str]:
    """
    Suggest possible object types based on geometry type.

    Args:
        geometry_type: GeoJSON geometry type

    Returns:
        List of compatible object types
    """
    result = []
    for obj_type, geom_type in GEOMETRY_TYPE_MAPPING.items():
        if geom_type == geometry_type:
            result.append(obj_type)
        # Also include types that can be converted
        elif geometry_type == 'MultiPolygon' and geom_type == 'Polygon':
            result.append(obj_type)
        elif geometry_type == 'MultiLineString' and geom_type == 'LineString':
            result.append(obj_type)
        elif geometry_type == 'MultiPoint' and geom_type == 'Point':
            result.append(obj_type)
        elif geometry_type in ('Polygon', 'MultiPolygon') and geom_type == 'Point':
            result.append(obj_type)  # Can use centroid

    return result


# ==============================================================================
# GEOJSON PARSING
# ==============================================================================

def parse_geojson(file_content: bytes) -> Dict[str, Any]:
    """
    Parse a GeoJSON file and return structured data.

    Args:
        file_content: Raw bytes of the GeoJSON file

    Returns:
        Dict with:
            - features: List of parsed features
            - detected_types: Dict mapping geometry types to counts
            - attributes: List of unique attribute names found
            - errors: List of parsing errors
    """
    result = {
        'features': [],
        'detected_types': {},
        'attributes': set(),
        'errors': [],
    }

    try:
        data = json.loads(file_content.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        result['errors'].append(f"JSON parsing error: {str(e)}")
        return result

    # Handle both FeatureCollection and single Feature
    if data.get('type') == 'FeatureCollection':
        features = data.get('features', [])
    elif data.get('type') == 'Feature':
        features = [data]
    else:
        result['errors'].append("Invalid GeoJSON: must be Feature or FeatureCollection")
        return result

    for idx, feature in enumerate(features):
        try:
            geometry = feature.get('geometry')
            properties = feature.get('properties', {}) or {}

            if not geometry:
                result['errors'].append(f"Feature {idx}: missing geometry")
                continue

            geom_type = geometry.get('type', 'Unknown')

            # Count geometry types
            result['detected_types'][geom_type] = result['detected_types'].get(geom_type, 0) + 1

            # Collect attribute names
            result['attributes'].update(properties.keys())

            # Suggest compatible object types
            compatible_types = detect_object_type_from_geometry(geom_type)

            # Parse feature
            parsed_feature = {
                'index': idx,
                'geometry': geometry,
                'geometry_type': geom_type,
                'properties': properties,
                'compatible_types': compatible_types,
            }

            result['features'].append(parsed_feature)

        except Exception as e:
            result['errors'].append(f"Feature {idx}: {str(e)}")

    result['attributes'] = list(result['attributes'])
    return result


# ==============================================================================
# KML PARSING
# ==============================================================================

def parse_kml(file_content: bytes) -> Dict[str, Any]:
    """
    Parse a KML/KMZ file and return structured data.

    Args:
        file_content: Raw bytes of the KML/KMZ file

    Returns:
        Dict with features, detected_types, attributes, errors
    """
    result = {
        'features': [],
        'detected_types': {},
        'attributes': set(),
        'errors': [],
    }

    # Check if it's a KMZ (ZIP containing KML)
    if file_content[:4] == b'PK\x03\x04':
        try:
            with zipfile.ZipFile(BytesIO(file_content)) as zf:
                kml_files = [f for f in zf.namelist() if f.endswith('.kml')]
                if not kml_files:
                    result['errors'].append("KMZ file contains no KML")
                    return result
                file_content = zf.read(kml_files[0])
        except zipfile.BadZipFile as e:
            result['errors'].append(f"Invalid KMZ file: {str(e)}")
            return result

    try:
        root = ET.fromstring(file_content)
    except ET.ParseError as e:
        result['errors'].append(f"KML parsing error: {str(e)}")
        return result

    # KML namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    # Find all Placemarks
    placemarks = root.findall('.//kml:Placemark', ns)
    if not placemarks:
        # Try without namespace
        placemarks = root.findall('.//Placemark')

    for idx, pm in enumerate(placemarks):
        try:
            # Get name
            name_elem = pm.find('kml:name', ns) or pm.find('name')
            name = name_elem.text if name_elem is not None else f"Feature {idx}"

            # Get description
            desc_elem = pm.find('kml:description', ns) or pm.find('description')
            description = desc_elem.text if desc_elem is not None else ""

            # Parse geometry
            geometry = None
            geom_type = None

            # Point
            point = pm.find('.//kml:Point/kml:coordinates', ns) or pm.find('.//Point/coordinates')
            if point is not None:
                coords = point.text.strip().split(',')
                geometry = {
                    'type': 'Point',
                    'coordinates': [float(coords[0]), float(coords[1])]
                }
                geom_type = 'Point'

            # LineString
            if geometry is None:
                linestring = pm.find('.//kml:LineString/kml:coordinates', ns) or pm.find('.//LineString/coordinates')
                if linestring is not None:
                    coords_list = []
                    for coord_str in linestring.text.strip().split():
                        parts = coord_str.split(',')
                        coords_list.append([float(parts[0]), float(parts[1])])
                    geometry = {
                        'type': 'LineString',
                        'coordinates': coords_list
                    }
                    geom_type = 'LineString'

            # Polygon
            if geometry is None:
                polygon = pm.find('.//kml:Polygon', ns) or pm.find('.//Polygon')
                if polygon is not None:
                    outer = polygon.find('.//kml:outerBoundaryIs/kml:LinearRing/kml:coordinates', ns)
                    if outer is None:
                        outer = polygon.find('.//outerBoundaryIs/LinearRing/coordinates')

                    if outer is not None:
                        coords_list = []
                        for coord_str in outer.text.strip().split():
                            parts = coord_str.split(',')
                            coords_list.append([float(parts[0]), float(parts[1])])
                        geometry = {
                            'type': 'Polygon',
                            'coordinates': [coords_list]
                        }
                        geom_type = 'Polygon'

            if geometry is None:
                result['errors'].append(f"Placemark {idx} ({name}): no recognizable geometry")
                continue

            # Count geometry types
            result['detected_types'][geom_type] = result['detected_types'].get(geom_type, 0) + 1

            # Collect attributes
            properties = {'name': name, 'description': description}

            # Parse ExtendedData
            ext_data = pm.find('.//kml:ExtendedData', ns) or pm.find('.//ExtendedData')
            if ext_data is not None:
                for data_elem in ext_data.findall('.//kml:Data', ns) or ext_data.findall('.//Data'):
                    key = data_elem.get('name', '')
                    value_elem = data_elem.find('kml:value', ns) or data_elem.find('value')
                    if key and value_elem is not None:
                        properties[key] = value_elem.text

            result['attributes'].update(properties.keys())

            compatible_types = detect_object_type_from_geometry(geom_type)

            parsed_feature = {
                'index': idx,
                'geometry': geometry,
                'geometry_type': geom_type,
                'properties': properties,
                'compatible_types': compatible_types,
            }

            result['features'].append(parsed_feature)

        except Exception as e:
            result['errors'].append(f"Placemark {idx}: {str(e)}")

    result['attributes'] = list(result['attributes'])
    return result


# ==============================================================================
# SHAPEFILE PARSING
# ==============================================================================

def parse_shapefile(file_content: bytes) -> Dict[str, Any]:
    """
    Parse a Shapefile (ZIP containing .shp, .shx, .dbf).

    Args:
        file_content: Raw bytes of the ZIP file

    Returns:
        Dict with features, detected_types, attributes, errors
    """
    result = {
        'features': [],
        'detected_types': {},
        'attributes': set(),
        'errors': [],
    }

    try:
        import fiona
    except ImportError:
        result['errors'].append("Fiona library not installed. Run: pip install fiona")
        return result

    # Create temp directory for shapefile extraction
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Extract ZIP
            with zipfile.ZipFile(BytesIO(file_content)) as zf:
                zf.extractall(tmpdir)

            # Find .shp file
            shp_files = [f for f in os.listdir(tmpdir) if f.endswith('.shp')]
            if not shp_files:
                # Check subdirectories
                for subdir in os.listdir(tmpdir):
                    subpath = os.path.join(tmpdir, subdir)
                    if os.path.isdir(subpath):
                        shp_files = [os.path.join(subdir, f) for f in os.listdir(subpath) if f.endswith('.shp')]
                        if shp_files:
                            break

            if not shp_files:
                result['errors'].append("No .shp file found in ZIP archive")
                return result

            shp_path = os.path.join(tmpdir, shp_files[0])

            # Read with fiona
            with fiona.open(shp_path, 'r') as src:
                # Get CRS info
                crs = src.crs

                for idx, feature in enumerate(src):
                    try:
                        geometry = feature['geometry']
                        properties = dict(feature['properties'])

                        geom_type = geometry['type']

                        # Count geometry types
                        result['detected_types'][geom_type] = result['detected_types'].get(geom_type, 0) + 1

                        # Collect attributes
                        result['attributes'].update(properties.keys())

                        compatible_types = detect_object_type_from_geometry(geom_type)

                        parsed_feature = {
                            'index': idx,
                            'geometry': geometry,
                            'geometry_type': geom_type,
                            'properties': properties,
                            'compatible_types': compatible_types,
                        }

                        result['features'].append(parsed_feature)

                    except Exception as e:
                        result['errors'].append(f"Feature {idx}: {str(e)}")

        except zipfile.BadZipFile:
            result['errors'].append("Invalid ZIP file")
        except Exception as e:
            result['errors'].append(f"Shapefile parsing error: {str(e)}")

    result['attributes'] = list(result['attributes'])
    return result


# ==============================================================================
# EXPORT FUNCTIONS
# ==============================================================================

def export_to_geojson(queryset, serializer_class=None) -> Dict:
    """
    Export a queryset to GeoJSON format.

    Args:
        queryset: Django queryset of geo objects
        serializer_class: Optional DRF serializer to use

    Returns:
        GeoJSON FeatureCollection dict
    """
    features = []

    for obj in queryset:
        # Get geometry
        geometry = None
        if hasattr(obj, 'geometry'):
            geometry = obj.geometry
        elif hasattr(obj, 'geometrie'):
            geometry = obj.geometrie
        elif hasattr(obj, 'geometrie_emprise'):
            geometry = obj.geometrie_emprise

        if geometry is None:
            continue

        # Build properties
        properties = {}
        for field in obj._meta.fields:
            field_name = field.name
            if field_name in ('geometry', 'geometrie', 'geometrie_emprise', 'centroid'):
                continue
            value = getattr(obj, field_name)
            # Handle FK
            if hasattr(value, 'pk'):
                properties[field_name] = value.pk
                if hasattr(value, 'nom'):
                    properties[f'{field_name}_nom'] = value.nom
                elif hasattr(value, 'nom_site'):
                    properties[f'{field_name}_nom'] = value.nom_site
            elif value is not None:
                properties[field_name] = value

        # Add object type
        properties['object_type'] = obj.__class__.__name__

        feature = {
            'type': 'Feature',
            'id': obj.pk,
            'geometry': json.loads(geometry.geojson),
            'properties': properties,
        }
        features.append(feature)

    return {
        'type': 'FeatureCollection',
        'features': features,
    }


def export_to_kml(queryset) -> str:
    """
    Export a queryset to KML format.

    Args:
        queryset: Django queryset of geo objects

    Returns:
        KML string
    """
    kml_header = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
<name>GreenSIG Export</name>
'''
    kml_footer = '''</Document>
</kml>'''

    placemarks = []

    for obj in queryset:
        # Get geometry
        geometry = None
        if hasattr(obj, 'geometry'):
            geometry = obj.geometry
        elif hasattr(obj, 'geometrie'):
            geometry = obj.geometrie
        elif hasattr(obj, 'geometrie_emprise'):
            geometry = obj.geometrie_emprise

        if geometry is None:
            continue

        # Get name
        name = getattr(obj, 'nom', None) or getattr(obj, 'nom_site', None) or f"{obj.__class__.__name__} {obj.pk}"

        # Build KML geometry
        kml_geom = ""
        if geometry.geom_type == 'Point':
            coords = f"{geometry.x},{geometry.y},0"
            kml_geom = f"<Point><coordinates>{coords}</coordinates></Point>"

        elif geometry.geom_type == 'LineString':
            coords = " ".join([f"{c[0]},{c[1]},0" for c in geometry.coords])
            kml_geom = f"<LineString><coordinates>{coords}</coordinates></LineString>"

        elif geometry.geom_type == 'Polygon':
            coords = " ".join([f"{c[0]},{c[1]},0" for c in geometry.exterior_ring.coords])
            kml_geom = f"""<Polygon>
<outerBoundaryIs><LinearRing><coordinates>{coords}</coordinates></LinearRing></outerBoundaryIs>
</Polygon>"""

        # Build description
        desc_parts = []
        for field in obj._meta.fields:
            field_name = field.name
            if field_name in ('geometry', 'geometrie', 'geometrie_emprise', 'centroid', 'id'):
                continue
            value = getattr(obj, field_name)
            if value is not None and not hasattr(value, 'pk'):
                desc_parts.append(f"{field_name}: {value}")
        description = "<br/>".join(desc_parts)

        placemark = f"""<Placemark>
<name>{name}</name>
<description><![CDATA[{description}]]></description>
{kml_geom}
</Placemark>"""
        placemarks.append(placemark)

    return kml_header + "\n".join(placemarks) + kml_footer


def export_to_shapefile(queryset, filename: str = 'export') -> bytes:
    """
    Export a queryset to Shapefile format (ZIP).

    Args:
        queryset: Django queryset of geo objects
        filename: Base filename for the shapefile

    Returns:
        ZIP file bytes containing .shp, .shx, .dbf, .prj
    """
    try:
        import fiona
        from fiona.crs import from_epsg
    except ImportError:
        raise ImportError("Fiona library not installed. Run: pip install fiona")

    # Determine geometry type from first object
    first_obj = queryset.first()
    if not first_obj:
        raise ValueError("Empty queryset")

    geometry = None
    if hasattr(first_obj, 'geometry'):
        geometry = first_obj.geometry
    elif hasattr(first_obj, 'geometrie'):
        geometry = first_obj.geometrie
    elif hasattr(first_obj, 'geometrie_emprise'):
        geometry = first_obj.geometrie_emprise

    if geometry is None:
        raise ValueError("No geometry found on objects")

    geom_type = geometry.geom_type

    # Build schema from model fields
    schema = {
        'geometry': geom_type,
        'properties': {}
    }

    for field in first_obj._meta.fields:
        field_name = field.name
        if field_name in ('geometry', 'geometrie', 'geometrie_emprise', 'centroid'):
            continue

        # Truncate field name to 10 chars for DBF
        short_name = field_name[:10]

        # Map Django field types to Fiona types
        field_type = field.get_internal_type()
        if field_type in ('IntegerField', 'AutoField', 'ForeignKey'):
            schema['properties'][short_name] = 'int'
        elif field_type in ('FloatField', 'DecimalField'):
            schema['properties'][short_name] = 'float'
        elif field_type in ('BooleanField',):
            schema['properties'][short_name] = 'bool'
        else:
            schema['properties'][short_name] = 'str'

    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        shp_path = os.path.join(tmpdir, f"{filename}.shp")

        # Write shapefile
        with fiona.open(
            shp_path, 'w',
            driver='ESRI Shapefile',
            crs=from_epsg(4326),
            schema=schema
        ) as dst:
            for obj in queryset:
                # Get geometry
                geom = None
                if hasattr(obj, 'geometry'):
                    geom = obj.geometry
                elif hasattr(obj, 'geometrie'):
                    geom = obj.geometrie
                elif hasattr(obj, 'geometrie_emprise'):
                    geom = obj.geometrie_emprise

                if geom is None:
                    continue

                # Build properties
                props = {}
                for field in obj._meta.fields:
                    field_name = field.name
                    if field_name in ('geometry', 'geometrie', 'geometrie_emprise', 'centroid'):
                        continue

                    short_name = field_name[:10]
                    value = getattr(obj, field_name)

                    # Handle FK
                    if hasattr(value, 'pk'):
                        props[short_name] = value.pk
                    elif value is not None:
                        props[short_name] = value
                    else:
                        props[short_name] = None

                # Write feature
                dst.write({
                    'geometry': json.loads(geom.geojson),
                    'properties': props,
                })

        # Create ZIP with all shapefile components
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for ext in ['.shp', '.shx', '.dbf', '.prj', '.cpg']:
                filepath = os.path.join(tmpdir, f"{filename}{ext}")
                if os.path.exists(filepath):
                    zf.write(filepath, f"{filename}{ext}")

        buffer.seek(0)
        return buffer.getvalue()


# ==============================================================================
# ATTRIBUTE MAPPING
# ==============================================================================

def apply_attribute_mapping(
    feature: Dict,
    mapping: Dict[str, str],
    target_type: str
) -> Dict[str, Any]:
    """
    Apply attribute mapping to convert source properties to target fields.

    Args:
        feature: Parsed feature with 'properties' dict
        mapping: Dict mapping source_attr -> target_field
        target_type: Target object type

    Returns:
        Dict of mapped attributes ready for model creation
    """
    source_props = feature.get('properties', {})
    target_fields = OBJECT_FIELDS.get(target_type, [])

    result = {}

    for source_attr, target_field in mapping.items():
        if target_field not in target_fields:
            continue

        value = source_props.get(source_attr)

        if value is None:
            continue

        # Apply transformations based on target field
        if target_field == 'taille':
            value = normalize_taille(value)
        elif target_field == 'densite':
            value = parse_densite(value)
        elif target_field in ('profondeur', 'diametre', 'puissance', 'debit', 'pression', 'volume', 'area_sqm', 'niveau_statique', 'niveau_dynamique'):
            value = parse_float(value)

        result[target_field] = value

    return result


def suggest_attribute_mapping(
    source_attributes: List[str],
    target_type: str
) -> Dict[str, str]:
    """
    Suggest automatic attribute mapping based on name similarity.

    Args:
        source_attributes: List of source attribute names
        target_type: Target object type

    Returns:
        Dict of suggested mappings (source -> target)
    """
    target_fields = OBJECT_FIELDS.get(target_type, [])
    suggestions = {}

    # Common synonyms
    synonyms = {
        'nom': ['name', 'nom', 'label', 'titre', 'title'],
        'famille': ['family', 'famille', 'type', 'espece', 'species'],
        'taille': ['size', 'taille', 'hauteur', 'height'],
        'densite': ['density', 'densite', 'densité'],
        'observation': ['description', 'observation', 'notes', 'comment', 'remarks'],
        'diametre': ['diameter', 'diametre', 'diamètre', 'diam'],
        'profondeur': ['depth', 'profondeur'],
        'materiau': ['material', 'materiau', 'matériau'],
        'pression': ['pressure', 'pression'],
        'volume': ['volume', 'capacity', 'capacite'],
        'puissance': ['power', 'puissance'],
        'debit': ['flow', 'debit', 'débit'],
        'marque': ['brand', 'marque', 'manufacturer'],
        'type': ['type', 'kind', 'category'],
    }

    for target_field in target_fields:
        possible_names = synonyms.get(target_field, [target_field])

        for source_attr in source_attributes:
            source_lower = source_attr.lower()
            if source_lower in possible_names or target_field in source_lower:
                suggestions[source_attr] = target_field
                break

    return suggestions
