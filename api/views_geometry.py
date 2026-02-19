# api/views_geometry.py
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import F
from django.contrib.gis.geos import GEOSGeometry
import json

from api_users.permissions import IsAdmin, IsAdminOrSuperviseur

from .models import (
    Site, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)
from .services.validation import (
    validate_geometry,
    detect_duplicates,
    find_existing_match,
    check_within_site,
    simplify_geometry,
    split_polygon,
    merge_polygons,
    calculate_geometry_metrics,
    buffer_geometry,
)


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


class GeometrySimplifyView(APIView):
    """
    POST /api/geometry/simplify/
    Simplifie une géométrie en réduisant le nombre de sommets.

    Permission: ADMIN ou SUPERVISEUR uniquement (modification de données GIS)

    Request body:
    {
        "geometry": { GeoJSON geometry },
        "tolerance": 0.0001,  // Optional, default 0.0001 degrees (~11m)
        "preserve_topology": true  // Optional, default true
    }

    Response:
    {
        "geometry": { simplified GeoJSON geometry },
        "stats": {
            "original_coords": 150,
            "simplified_coords": 45,
            "reduction_percent": 70.0,
            ...
        }
    }
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperviseur]

    def post(self, request):
        geometry_data = request.data.get('geometry')
        tolerance = request.data.get('tolerance', 0.0001)
        preserve_topology = request.data.get('preserve_topology', True)

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)

        try:
            # Convert GeoJSON to GEOS geometry
            geom = GEOSGeometry(json.dumps(geometry_data))

            # Simplify
            simplified, stats = simplify_geometry(
                geom,
                tolerance=tolerance,
                preserve_topology=preserve_topology
            )

            # Convert back to GeoJSON
            simplified_geojson = json.loads(simplified.geojson)

            return Response({
                'geometry': simplified_geojson,
                'stats': stats
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometrySplitView(APIView):
    """
    POST /api/geometry/split/
    Divise un polygone avec une ligne de coupe.

    Permission: ADMIN ou SUPERVISEUR uniquement (modification de données GIS)

    Request body:
    {
        "polygon": { GeoJSON Polygon },
        "split_line": { GeoJSON LineString }
    }

    Response:
    {
        "geometries": [ { GeoJSON Polygon }, ... ],
        "stats": {
            "success": true,
            "num_parts": 2,
            "areas": [0.001, 0.002]
        }
    }
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperviseur]

    def post(self, request):
        polygon_data = request.data.get('polygon')
        split_line_data = request.data.get('split_line')

        if not polygon_data:
            return Response({'error': 'polygon is required'}, status=400)
        if not split_line_data:
            return Response({'error': 'split_line is required'}, status=400)

        try:
            polygon = GEOSGeometry(json.dumps(polygon_data))
            split_line = GEOSGeometry(json.dumps(split_line_data))

            if polygon.geom_type not in ('Polygon', 'MultiPolygon'):
                return Response({'error': 'First geometry must be a Polygon'}, status=400)
            if split_line.geom_type != 'LineString':
                return Response({'error': 'Split line must be a LineString'}, status=400)

            result_polygons, stats = split_polygon(polygon, split_line)

            # Convert to GeoJSON
            geometries = [json.loads(p.geojson) for p in result_polygons]

            return Response({
                'geometries': geometries,
                'stats': stats
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometryMergeView(APIView):
    """
    POST /api/geometry/merge/
    Fusionne plusieurs polygones en un seul.

    Permission: ADMIN ou SUPERVISEUR uniquement (modification de données GIS)

    Request body:
    {
        "polygons": [ { GeoJSON Polygon }, { GeoJSON Polygon }, ... ]
    }

    Response:
    {
        "geometry": { GeoJSON Polygon or MultiPolygon },
        "stats": {
            "success": true,
            "input_count": 3,
            "output_type": "Polygon",
            ...
        }
    }
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperviseur]

    def post(self, request):
        polygons_data = request.data.get('polygons', [])

        if not polygons_data or len(polygons_data) < 2:
            return Response({'error': 'At least 2 polygons are required'}, status=400)

        try:
            polygons = []
            for i, poly_data in enumerate(polygons_data):
                poly = GEOSGeometry(json.dumps(poly_data))
                if poly.geom_type not in ('Polygon', 'MultiPolygon'):
                    return Response({
                        'error': f'Geometry at index {i} must be a Polygon'
                    }, status=400)
                polygons.append(poly)

            result, stats = merge_polygons(polygons)

            if result is None:
                return Response({
                    'geometry': None,
                    'stats': stats
                }, status=400)

            return Response({
                'geometry': json.loads(result.geojson),
                'stats': stats
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometryValidateView(APIView):
    """
    POST /api/geometry/validate/
    Valide une géométrie et détecte les doublons potentiels.

    Request body:
    {
        "geometry": { GeoJSON geometry },
        "target_type": "Arbre",  // Optional, for duplicate detection
        "site_id": 1,  // Optional, for duplicate detection and boundary check
        "check_duplicates": true,  // Optional
        "check_within_site": true,  // Optional
        "duplicate_tolerance": 0.0001  // Optional, degrees
    }

    Response:
    {
        "validation": {
            "is_valid": true,
            "errors": [],
            "warnings": []
        },
        "duplicates": [...],  // If check_duplicates=true
        "within_site": {...}  // If check_within_site=true
    }
    """

    def post(self, request):
        geometry_data = request.data.get('geometry')
        target_type = request.data.get('target_type')
        site_id = request.data.get('site_id')
        check_dup = request.data.get('check_duplicates', False)
        check_site = request.data.get('check_within_site', False)
        dup_tolerance = request.data.get('duplicate_tolerance', 0.0001)

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)

        try:
            geom = GEOSGeometry(json.dumps(geometry_data))

            response_data = {}

            # Basic validation
            response_data['validation'] = validate_geometry(geom)

            # Duplicate detection
            if check_dup and target_type:
                model_class = _get_model_class(target_type)
                if model_class:
                    response_data['duplicates'] = detect_duplicates(
                        geom,
                        model_class,
                        site_id=site_id,
                        tolerance=dup_tolerance
                    )
                else:
                    response_data['duplicates'] = []
                    response_data['validation']['warnings'].append({
                        'code': 'UNKNOWN_TYPE',
                        'message': f'Unknown target type: {target_type}'
                    })

            # Within site check
            if check_site and site_id:
                response_data['within_site'] = check_within_site(geom, site_id)

            return Response(response_data)

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometryCalculateView(APIView):
    """
    POST /api/geometry/calculate/
    Calcule les métriques d'une géométrie (aire, longueur, périmètre, etc.).

    Request body:
    {
        "geometry": { GeoJSON geometry }
    }

    Response:
    {
        "metrics": {
            "geometry_type": "Polygon",
            "area_m2": 1234.56,
            "area_hectares": 0.1234,
            "perimeter_m": 456.78,
            "centroid": { "lng": -7.5, "lat": 33.5 },
            "bbox": { "min_lng": ..., ... }
        }
    }
    """

    def post(self, request):
        geometry_data = request.data.get('geometry')

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)

        try:
            geom = GEOSGeometry(json.dumps(geometry_data))
            metrics = calculate_geometry_metrics(geom)

            return Response({'metrics': metrics})

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometryBufferView(APIView):
    """
    POST /api/geometry/buffer/
    Crée un buffer (zone tampon) autour d'une géométrie.

    Permission: ADMIN ou SUPERVISEUR uniquement (modification de données GIS)

    Request body:
    {
        "geometry": { GeoJSON geometry },
        "distance": 10,  // Distance in meters
        "quad_segs": 8  // Optional, segments for curves (default 8)
    }

    Response:
    {
        "geometry": { GeoJSON Polygon },
        "stats": {
            "input_type": "Point",
            "output_type": "Polygon",
            "distance_meters": 10
        }
    }
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperviseur]

    def post(self, request):
        geometry_data = request.data.get('geometry')
        distance = request.data.get('distance')
        quad_segs = request.data.get('quad_segs', 8)

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)
        if distance is None:
            return Response({'error': 'distance (in meters) is required'}, status=400)

        try:
            geom = GEOSGeometry(json.dumps(geometry_data))
            buffered, stats = buffer_geometry(geom, distance, quad_segs)

            return Response({
                'geometry': json.loads(buffered.geojson),
                'stats': stats
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)


# ==============================================================================
# ENDPOINT POUR RÉCUPÉRER LES OBJETS DANS UNE GÉOMÉTRIE
# ==============================================================================

class ObjectsInGeometryView(APIView):
    """
    POST /api/objects-in-geometry/
    Récupère tous les objets GIS qui intersectent avec une géométrie donnée.

    Utilisé notamment pour récupérer les objets dans la zone d'une réclamation.

    Request body:
    {
        "geometry": { GeoJSON geometry (Point, Polygon, etc.) },
        "site_id": 123,  // Optional: filtrer par site
        "object_types": ["Arbre", "Gazon"]  // Optional: filtrer par types (tous par défaut)
    }

    Response:
    {
        "objects": [
            {"id": 1, "type": "Arbre", "nom": "Olivier 1", "site_id": 1, "site_nom": "Jardin A"},
            ...
        ],
        "count": 15,
        "by_type": {"Arbre": 10, "Gazon": 5}
    }
    """

    def post(self, request):
        geometry_data = request.data.get('geometry')
        site_id = request.data.get('site_id')
        object_types = request.data.get('object_types')  # Liste de types à inclure

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)

        try:
            # Convert GeoJSON to GEOS geometry
            # La géométrie peut arriver sous différentes formes
            if isinstance(geometry_data, str):
                # Déjà une chaîne JSON/WKT
                geom = GEOSGeometry(geometry_data)
            elif isinstance(geometry_data, dict):
                # Objet GeoJSON dict
                geom = GEOSGeometry(json.dumps(geometry_data))
            else:
                return Response({
                    'error': f'Format de géométrie invalide: attendu dict ou str, reçu {type(geometry_data).__name__}',
                    'received_type': type(geometry_data).__name__
                }, status=400)

            # Mapping type -> model
            type_mapping = {
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
                'Canalisation': Canalisation,
                'Aspersion': Aspersion,
                'Goutte': Goutte,
                'Ballon': Ballon,
            }

            # Déterminer quels types charger
            if object_types:
                types_to_load = [t for t in object_types if t in type_mapping]
            else:
                types_to_load = list(type_mapping.keys())

            results = []
            by_type = {}

            for type_name in types_to_load:
                Model = type_mapping[type_name]

                # Query avec filtre géométrique
                queryset = Model.objects.filter(
                    geometry__intersects=geom
                ).select_related('site', 'sous_site')

                # Filtrer par site si spécifié
                if site_id:
                    queryset = queryset.filter(site_id=site_id)

                # Récupérer les objets
                objects = queryset.values(
                    'id', 'site_id', 'sous_site_id'
                ).annotate(
                    site_nom=F('site__nom_site'),
                    sous_site_nom=F('sous_site__nom')
                )

                # Ajouter le nom si le modèle a un champ 'nom'
                if hasattr(Model, 'nom'):
                    objects = queryset.values(
                        'id', 'nom', 'site_id', 'sous_site_id'
                    ).annotate(
                        site_nom=F('site__nom_site'),
                        sous_site_nom=F('sous_site__nom')
                    )

                count = 0
                for obj in objects:
                    obj['type'] = type_name
                    # Utiliser objet_ptr_id comme ID unifié (hérite de Objet)
                    obj['objet_id'] = obj['id']
                    results.append(obj)
                    count += 1

                if count > 0:
                    by_type[type_name] = count

            return Response({
                'objects': results,
                'count': len(results),
                'by_type': by_type
            })

        except Exception as e:
            import traceback
            return Response({
                'error': str(e),
                'traceback': traceback.format_exc()
            }, status=400)
