# api/views_import.py
import logging
import json

from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse
from django.db import transaction
from django.contrib.gis.geos import GEOSGeometry

from api_users.permissions import IsAdmin

from .models import (
    Site, SousSite, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)
from .services.geo_io import (
    parse_geojson, parse_kml, parse_shapefile,
    convert_geometry, validate_geometry_for_type,
    export_to_geojson, export_to_kml, export_to_shapefile,
    apply_attribute_mapping, suggest_attribute_mapping,
    GEOMETRY_TYPE_MAPPING, OBJECT_FIELDS
)
from .services.validation import validate_geometry, find_existing_match

logger = logging.getLogger(__name__)


def _get_model_class(target_type):
    """Get Django model class from type name."""
    model_mapping = {
        'Site': Site,
        'Arbre': Arbre,
        'Gazon': Gazon,
        'Palmier': Palmier,
        'Arbuste': Arbuste,
        'Vivace': Vivace,
        'Cactus': Cactus,
        'Graminee': Graminee,
        'Puit': Puit,
        'Pompe': Pompe,
        'Vanne': Vanne,
        'Clapet': Clapet,
        'Ballon': Ballon,
        'Canalisation': Canalisation,
        'Aspersion': Aspersion,
        'Goutte': Goutte,
    }
    return model_mapping.get(target_type)


class GeoImportPreviewView(APIView):
    """
    Preview imported geo data before validation.

    POST /api/import/preview/
    Content-Type: multipart/form-data

    Permission: ADMIN uniquement (import de données sensibles)

    Body:
        - file: The geo file (GeoJSON, KML, KMZ, or ZIP with Shapefile)
        - format: 'geojson' | 'kml' | 'shapefile' (auto-detected if not provided)

    Returns:
        {
            "features": [
                {
                    "index": 0,
                    "geometry": {...},
                    "geometry_type": "Point",
                    "properties": {...},
                    "compatible_types": ["Arbre", "Palmier", "Puit", ...]
                },
                ...
            ],
            "detected_types": {"Point": 10, "Polygon": 5},
            "attributes": ["name", "description", "type", ...],
            "suggested_mapping": {...},
            "errors": []
        }
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        file_format = request.data.get('format', '').lower()

        # Auto-detect format from filename
        filename = file_obj.name.lower()
        if not file_format or file_format == 'auto':
            if filename.endswith('.geojson') or filename.endswith('.json'):
                file_format = 'geojson'
            elif filename.endswith('.kml') or filename.endswith('.kmz'):
                file_format = 'kml'
            elif filename.endswith('.zip'):
                file_format = 'shapefile'
            else:
                return Response({'error': 'Could not detect file format. Please specify format parameter.'}, status=400)

        # Read file content
        file_content = file_obj.read()

        # Parse based on format
        if file_format == 'geojson':
            result = parse_geojson(file_content)
        elif file_format == 'kml':
            result = parse_kml(file_content)
        elif file_format == 'shapefile':
            result = parse_shapefile(file_content)
        else:
            return Response({'error': f'Unsupported format: {file_format}'}, status=400)

        # Transform response to match frontend expectations
        detected_types = result.get('detected_types', {})
        attributes = result.get('attributes', [])
        features = result.get('features', [])

        # Add suggested mapping if we have features
        suggested_mapping = {}
        if features and attributes:
            if detected_types:
                most_common_geom = max(detected_types.keys(), key=lambda k: detected_types[k])
                compatible = features[0].get('compatible_types', [])
                if compatible:
                    suggested_mapping = suggest_attribute_mapping(
                        attributes,
                        compatible[0]
                    )

        # Build response matching frontend ImportPreviewResponse interface
        response_data = {
            'format': file_format,
            'feature_count': len(features),
            'geometry_types': list(detected_types.keys()),
            'sample_properties': attributes,
            'features': features,
            'suggested_mapping': suggested_mapping,
            'errors': result.get('errors', []),
        }

        return Response(response_data)


class GeoImportValidateView(APIView):
    """
    Validate imported features before execution.

    POST /api/import/validate/

    Permission: ADMIN uniquement (import de données sensibles)

    Body:
        {
            "features": [...],  // From preview response
            "mapping": {        // Attribute mapping
                "source_attr": "target_field",
                ...
            },
            "target_type": "Arbre",  // Target object type
            "site_id": 1             // Target site ID
        }

    Returns:
        {
            "valid": true|false,
            "valid_count": 10,
            "errors": [
                {"index": 0, "error": "..."},
                ...
            ],
            "warnings": [
                {"index": 1, "warning": "Duplicate detected at ..."},
                ...
            ]
        }
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request):
        features = request.data.get('features', [])
        mapping = request.data.get('mapping', {})
        target_type = request.data.get('target_type')
        site_id = request.data.get('site_id')
        auto_detect_site = request.data.get('auto_detect_site', False)
        import_mode = request.data.get('import_mode', 'create')

        if import_mode not in ('create', 'skip_duplicates'):
            import_mode = 'create'

        if not features:
            return Response({'error': 'No features provided'}, status=400)

        if not target_type:
            return Response({'error': 'target_type is required'}, status=400)

        if target_type not in GEOMETRY_TYPE_MAPPING:
            return Response({'error': f'Invalid target_type: {target_type}'}, status=400)

        # Site is not required for Site objects
        site = None
        all_sites = None  # For auto-detect mode
        if target_type != 'Site':
            if auto_detect_site:
                # Load all active sites for geometry-based detection
                all_sites = list(Site.objects.filter(actif=True))
                if not all_sites:
                    return Response({'error': 'No active sites found for auto-detection'}, status=400)
            elif not site_id:
                return Response({'error': 'site_id is required (or enable auto_detect_site)'}, status=400)
            else:
                # Verify site exists
                try:
                    site = Site.objects.get(pk=site_id)
                except Site.DoesNotExist:
                    return Response({'error': f'Site {site_id} not found'}, status=400)

        errors = []
        warnings = []
        valid_count = 0
        invalid_count = 0
        existing_count = 0
        validated_features = []

        expected_geom_type = GEOMETRY_TYPE_MAPPING[target_type]

        for feature in features:
            idx = feature.get('index', 0)
            geometry = feature.get('geometry')
            properties = feature.get('properties', {})
            is_valid = True

            if not geometry:
                errors.append({'index': idx, 'message': 'Missing geometry', 'code': 'MISSING_GEOMETRY'})
                is_valid = False
                invalid_count += 1
                validated_features.append({
                    'index': idx,
                    'is_valid': False,
                    'geometry_type': 'Unknown',
                    'mapped_properties': {}
                })
                continue

            geom_type = geometry.get('type', 'Unknown')

            # Validate geometry type
            geos_geom = GEOSGeometry(json.dumps(geometry), srid=4326)
            geom_valid, error_msg = validate_geometry_for_type(
                geos_geom,
                target_type
            )

            if not geom_valid:
                errors.append({'index': idx, 'message': error_msg, 'code': 'INVALID_GEOMETRY'})
                is_valid = False
                invalid_count += 1
                validated_features.append({
                    'index': idx,
                    'is_valid': False,
                    'geometry_type': geom_type,
                    'mapped_properties': {}
                })
                continue

            # Topological validation
            topo_result = validate_geometry(geos_geom)
            if not topo_result['is_valid']:
                topo_errors = [e.get('message', str(e)) for e in topo_result.get('errors', [])]
                errors.append({
                    'index': idx,
                    'message': f"Topology errors: {'; '.join(topo_errors)}",
                    'code': 'TOPOLOGY_ERROR'
                })
                is_valid = False
                invalid_count += 1
                validated_features.append({
                    'index': idx,
                    'is_valid': False,
                    'geometry_type': geom_type,
                    'mapped_properties': {}
                })
                continue

            # Add topology warnings if any
            for tw in topo_result.get('warnings', []):
                warnings.append({
                    'index': idx,
                    'message': tw.get('message', str(tw)),
                    'code': 'TOPOLOGY_WARNING'
                })

            # Check if geometry is within site boundary (only for non-Site objects)
            try:
                geom, conversion_warnings = convert_geometry(geometry, expected_geom_type)
                for cw in conversion_warnings:
                    warnings.append({'index': idx, 'message': cw, 'code': 'CONVERSION_WARNING'})
                detected_site = site  # Use provided site by default

                if auto_detect_site and all_sites:
                    # Auto-detect: find the site that contains this geometry
                    detected_site = None
                    for candidate_site in all_sites:
                        if candidate_site.geometrie_emprise:
                            if candidate_site.geometrie_emprise.contains(geom) or candidate_site.geometrie_emprise.intersects(geom):
                                detected_site = candidate_site
                                break

                    if not detected_site:
                        errors.append({
                            'index': idx,
                            'message': 'Geometry is not within any site boundary',
                            'code': 'NO_SITE_FOUND'
                        })
                        is_valid = False
                        invalid_count += 1
                        validated_features.append({
                            'index': idx,
                            'is_valid': False,
                            'geometry_type': geom_type,
                            'mapped_properties': {},
                            'detected_site_id': None
                        })
                        continue

                elif detected_site and detected_site.geometrie_emprise:
                    # Manual mode: check if geometry is within selected site
                    if not detected_site.geometrie_emprise.contains(geom) and not detected_site.geometrie_emprise.intersects(geom):
                        warnings.append({
                            'index': idx,
                            'message': 'Geometry is outside site boundary',
                            'code': 'OUTSIDE_BOUNDARY'
                        })
            except Exception as e:
                errors.append({'index': idx, 'message': f'Geometry conversion error: {str(e)}', 'code': 'CONVERSION_ERROR'})
                is_valid = False
                invalid_count += 1
                validated_features.append({
                    'index': idx,
                    'is_valid': False,
                    'geometry_type': geom_type,
                    'mapped_properties': {}
                })
                continue

            # Apply mapping to get mapped properties preview
            mapped_props = apply_attribute_mapping(feature, mapping, target_type)

            # Duplicate / existing match check
            try:
                from django.contrib.gis.db.models.functions import Distance
                from django.contrib.gis.measure import D

                model_class = _get_model_class(target_type)
                if model_class and import_mode == 'skip_duplicates':
                    # Skip duplicates mode: find existing match
                    check_site = detected_site if auto_detect_site else site
                    match = find_existing_match(
                        geometry=geom,
                        model_class=model_class,
                        site_id=check_site.pk if check_site else None,
                        target_type=target_type,
                        mapped_properties=mapped_props,
                        tolerance_meters=5.0,
                    )
                    if match:
                        existing_count += 1
                        feature_result = {
                            'index': idx,
                            'is_valid': True,
                            'is_existing': True,
                            'existing_match': match,
                            'geometry_type': geom_type,
                            'mapped_properties': mapped_props,
                        }
                        if auto_detect_site and detected_site:
                            feature_result['detected_site_id'] = detected_site.pk
                            feature_result['detected_site_name'] = detected_site.nom_site
                        validated_features.append(feature_result)
                        continue
                elif model_class:
                    # Create mode: just warn about duplicates
                    if target_type == 'Site':
                        nearby = model_class.objects.filter(
                            geometrie_emprise__intersects=geom
                        ).exists()
                    else:
                        check_site = detected_site if auto_detect_site else site
                        if check_site:
                            nearby = model_class.objects.filter(
                                site=check_site,
                                geometry__distance_lte=(geom, D(m=1))
                            ).exists()
                        else:
                            nearby = False
                    if nearby:
                        warnings.append({
                            'index': idx,
                            'message': 'Possible duplicate: object exists within 1m' if target_type != 'Site' else 'Possible duplicate: site with overlapping geometry exists',
                            'code': 'DUPLICATE'
                        })
            except Exception as e:
                logger.warning(f"Duplicate check failed for feature {idx}: {e}")

            valid_count += 1
            feature_result = {
                'index': idx,
                'is_valid': True,
                'is_existing': False,
                'geometry_type': geom_type,
                'mapped_properties': mapped_props
            }

            # Include detected site info if in auto-detect mode
            if auto_detect_site and detected_site:
                feature_result['detected_site_id'] = detected_site.pk
                feature_result['detected_site_name'] = detected_site.nom_site

            validated_features.append(feature_result)

        return Response({
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'existing_count': existing_count,
            'import_mode': import_mode,
            'errors': errors,
            'warnings': warnings,
            'features': validated_features
        })



class GeoImportExecuteView(APIView):
    """
    Execute the import and create objects in database.

    POST /api/import/execute/

    Permission: ADMIN uniquement (création de données en masse)

    Body:
        {
            "features": [...],
            "mapping": {...},
            "target_type": "Arbre",
            "site_id": 1,
            "sous_site_id": null  // Optional
        }

    Returns:
        {
            "created": [1, 2, 3, ...],  // IDs of created objects
            "errors": [
                {"index": 0, "error": "..."},
                ...
            ],
            "summary": {
                "total": 10,
                "created": 8,
                "failed": 2
            }
        }
    """
    permission_classes = [permissions.IsAuthenticated, IsAdmin]

    def post(self, request):
        features = request.data.get('features', [])
        mapping = request.data.get('mapping', {})
        target_type = request.data.get('target_type')
        site_id = request.data.get('site_id')
        sous_site_id = request.data.get('sous_site_id')
        auto_detect_site = request.data.get('auto_detect_site', False)
        import_mode = request.data.get('import_mode', 'create')

        if import_mode not in ('create', 'skip_duplicates'):
            import_mode = 'create'

        if not features:
            return Response({'error': 'No features provided'}, status=400)

        if not target_type or target_type not in GEOMETRY_TYPE_MAPPING:
            return Response({'error': 'Invalid target_type'}, status=400)

        # Site is not required for Site objects
        site = None
        sous_site = None
        all_sites = None  # For auto-detect mode
        if target_type != 'Site':
            if auto_detect_site:
                # Load all active sites for geometry-based detection
                all_sites = list(Site.objects.filter(actif=True))
                if not all_sites:
                    return Response({'error': 'No active sites found for auto-detection'}, status=400)
            elif not site_id:
                return Response({'error': 'site_id is required (or enable auto_detect_site)'}, status=400)
            else:
                # Get site and optionally sous_site
                try:
                    site = Site.objects.get(pk=site_id)
                except Site.DoesNotExist:
                    return Response({'error': f'Site {site_id} not found'}, status=400)

            if sous_site_id:
                try:
                    sous_site = SousSite.objects.get(pk=sous_site_id)
                except SousSite.DoesNotExist:
                    return Response({'error': f'SousSite {sous_site_id} not found'}, status=400)

        # Get model class
        model_class = _get_model_class(target_type)
        if not model_class:
            return Response({'error': f'Unknown model for type: {target_type}'}, status=400)

        expected_geom_type = GEOMETRY_TYPE_MAPPING[target_type]

        created_ids = []
        skipped_ids = []
        errors = []

        try:
            with transaction.atomic():
                for feature in features:
                    idx = feature.get('index', 0)

                    try:
                        geometry = feature.get('geometry')
                        if not geometry:
                            errors.append({'index': idx, 'error': 'Missing geometry'})
                            continue

                        # Convert geometry
                        geom, _ = convert_geometry(geometry, expected_geom_type)

                        # Apply attribute mapping
                        attributes = apply_attribute_mapping(feature, mapping, target_type)

                        # Handle Site objects differently
                        if target_type == 'Site':
                            # Sites have different field names
                            attributes['geometrie_emprise'] = geom
                            attributes['centroid'] = geom.centroid
                            attributes['actif'] = True
                            # Set default name if not provided
                            if 'nom_site' not in attributes:
                                props = feature.get('properties', {})
                                attributes['nom_site'] = props.get('name') or props.get('nom') or f"Site Import {idx + 1}"
                            # Set default code if not provided
                            if 'code_site' not in attributes:
                                import uuid
                                attributes['code_site'] = f"SITE_{uuid.uuid4().hex[:8].upper()}"

                            # Skip duplicates check for Site
                            if import_mode == 'skip_duplicates':
                                # Use original mapped properties (before auto-generated code_site)
                                original_props = apply_attribute_mapping(feature, mapping, target_type)
                                match = find_existing_match(
                                    geometry=geom,
                                    model_class=model_class,
                                    site_id=None,
                                    target_type=target_type,
                                    mapped_properties=original_props,
                                )
                                if match:
                                    skipped_ids.append(match['id'])
                                    continue
                        else:
                            # Add required fields for other objects
                            # Determine the site for this feature
                            target_site = site  # Use provided site by default

                            if auto_detect_site and all_sites:
                                # Auto-detect: find the site that contains this geometry
                                target_site = None
                                for candidate_site in all_sites:
                                    if candidate_site.geometrie_emprise:
                                        if candidate_site.geometrie_emprise.contains(geom) or candidate_site.geometrie_emprise.intersects(geom):
                                            target_site = candidate_site
                                            break

                                if not target_site:
                                    errors.append({'index': idx, 'error': 'Geometry is not within any site boundary'})
                                    continue

                            attributes['site'] = target_site
                            if sous_site:
                                attributes['sous_site'] = sous_site
                            attributes['geometry'] = geom

                            # Set default name if not provided
                            if 'nom' not in attributes and 'nom' in OBJECT_FIELDS.get(target_type, []):
                                attributes['nom'] = f"{target_type} Import {idx + 1}"

                            # Skip duplicates check for non-Site objects
                            if import_mode == 'skip_duplicates':
                                # Use original mapped properties (before auto-generated nom)
                                original_props = apply_attribute_mapping(feature, mapping, target_type)
                                match = find_existing_match(
                                    geometry=geom,
                                    model_class=model_class,
                                    site_id=target_site.pk if target_site else None,
                                    target_type=target_type,
                                    mapped_properties=original_props,
                                )
                                if match:
                                    skipped_ids.append(match['id'])
                                    continue

                        # Create object
                        obj = model_class.objects.create(**attributes)
                        created_ids.append(obj.pk)

                    except Exception as e:
                        errors.append({'index': idx, 'error': str(e)})

                # If any errors occurred, rollback all created objects
                if errors:
                    transaction.set_rollback(True)
                    created_ids = []
        except Exception as e:
            logger.error(f"Import transaction failed: {e}")
            return Response({
                'created': [],
                'skipped': [],
                'errors': [{'index': -1, 'error': f'Transaction failed: {str(e)}'}],
                'summary': {
                    'total': len(features),
                    'created': 0,
                    'skipped': 0,
                    'failed': len(features)
                },
                'rolled_back': True
            })

        rolled_back = len(errors) > 0
        return Response({
            'created': created_ids,
            'skipped': skipped_ids,
            'errors': errors,
            'summary': {
                'total': len(features),
                'created': len(created_ids),
                'skipped': len(skipped_ids),
                'failed': len(errors)
            },
            'rolled_back': rolled_back
        })
