# api/services/__init__.py
"""
Services module for GreenSIG API.
Contains reusable business logic for geo operations, import/export, validation.
"""

from .geo_io import (
    parse_geojson,
    parse_kml,
    parse_shapefile,
    convert_geometry,
    validate_geometry_for_type,
    export_to_geojson,
    export_to_kml,
    export_to_shapefile,
    GEOMETRY_TYPE_MAPPING,
)

from .validation import (
    validate_geometry,
    detect_duplicates,
    check_within_site,
    simplify_geometry,
    split_polygon,
    merge_polygons,
    calculate_geometry_metrics,
    buffer_geometry,
)

__all__ = [
    # geo_io
    'parse_geojson',
    'parse_kml',
    'parse_shapefile',
    'convert_geometry',
    'validate_geometry_for_type',
    'export_to_geojson',
    'export_to_kml',
    'export_to_shapefile',
    'GEOMETRY_TYPE_MAPPING',
    # validation
    'validate_geometry',
    'detect_duplicates',
    'check_within_site',
    'simplify_geometry',
    'split_polygon',
    'merge_polygons',
    'calculate_geometry_metrics',
    'buffer_geometry',
]
