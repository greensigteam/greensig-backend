# api/serializers.py
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework_gis.fields import GeometryField
from rest_framework import serializers
from .models import (
    Site, SousSite, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)


# ==============================================================================
# SERIALIZERS POUR LA HIÉRARCHIE SPATIALE
# ==============================================================================

class SiteSerializer(GeoFeatureModelSerializer):
    geometrie_emprise = GeometryField()
    centroid = GeometryField(read_only=True)  # Auto-calculated from geometrie_emprise
    code_site = serializers.CharField(read_only=True)  # Auto-generated
    client_nom = serializers.SerializerMethodField()

    class Meta:
        model = Site
        geo_field = "geometrie_emprise"
        fields = (
            'id', 'nom_site', 'adresse', 'superficie_totale', 'code_site',
            'client', 'client_nom',
            'date_debut_contrat', 'date_fin_contrat', 'actif', 'centroid'
        )

    def get_client_nom(self, obj):
        """Return client name or None if no client assigned"""
        return obj.client.nom_structure if obj.client else None


class SousSiteSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    geometrie = GeometryField()

    class Meta:
        model = SousSite
        geo_field = "geometrie"
        fields = ('id', 'site', 'site_nom', 'nom')


# ==============================================================================
# SERIALIZERS POUR LES VÉGÉTAUX
# ==============================================================================

class ArbreSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Arbre
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'taille', 'symbole', 'observation', 'last_intervention_date', 'etat'
        )


class GazonSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()
    superficie_calculee = serializers.SerializerMethodField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None
    
    def get_superficie_calculee(self, obj):
        """Calculate area in square meters using PostGIS ST_Area with geography."""
        if obj.geometry:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ST_Area(%s::geography)",
                    [obj.geometry.ewkt]
                )
                result = cursor.fetchone()
                return round(result[0], 2) if result and result[0] else None
        return None

    class Meta:
        model = Gazon
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'area_sqm', 'superficie_calculee', 'observation', 'last_intervention_date', 'etat'
        )


class PalmierSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Palmier
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'taille', 'symbole', 'observation', 'last_intervention_date', 'etat'
        )


class ArbusteSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()
    superficie_calculee = serializers.SerializerMethodField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None
    
    def get_superficie_calculee(self, obj):
        """Calculate area in square meters using PostGIS ST_Area with geography."""
        if obj.geometry:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ST_Area(%s::geography)",
                    [obj.geometry.ewkt]
                )
                result = cursor.fetchone()
                return round(result[0], 2) if result and result[0] else None
        return None

    class Meta:
        model = Arbuste
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'densite', 'superficie_calculee', 'symbole', 'observation', 'last_intervention_date', 'etat'
        )


class VivaceSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()
    superficie_calculee = serializers.SerializerMethodField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None
    
    def get_superficie_calculee(self, obj):
        """Calculate area in square meters using PostGIS ST_Area with geography."""
        if obj.geometry:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ST_Area(%s::geography)",
                    [obj.geometry.ewkt]
                )
                result = cursor.fetchone()
                return round(result[0], 2) if result and result[0] else None
        return None

    class Meta:
        model = Vivace
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'nom', 'famille', 'densite', 'superficie_calculee', 'observation', 'last_intervention_date'
        )


class CactusSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()
    superficie_calculee = serializers.SerializerMethodField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None
    
    def get_superficie_calculee(self, obj):
        """Calculate area in square meters using PostGIS ST_Area with geography."""
        if obj.geometry:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ST_Area(%s::geography)",
                    [obj.geometry.ewkt]
                )
                result = cursor.fetchone()
                return round(result[0], 2) if result and result[0] else None
        return None

    class Meta:
        model = Cactus
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'nom', 'famille', 'densite', 'superficie_calculee', 'observation', 'last_intervention_date'
        )


class GramineeSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()
    superficie_calculee = serializers.SerializerMethodField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None
    
    def get_superficie_calculee(self, obj):
        """Calculate area in square meters using PostGIS ST_Area with geography."""
        if obj.geometry:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ST_Area(%s::geography)",
                    [obj.geometry.ewkt]
                )
                result = cursor.fetchone()
                return round(result[0], 2) if result and result[0] else None
        return None

    class Meta:
        model = Graminee
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'nom', 'famille', 'densite', 'symbole', 'superficie_calculee', 'observation', 'last_intervention_date'
        )


# ==============================================================================
# SERIALIZERS POUR L'HYDRAULIQUE
# ==============================================================================

class PuitSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Puit
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'nom', 'profondeur', 'diametre', 'niveau_statique',
            'niveau_dynamique', 'symbole', 'observation', 'last_intervention_date'
        )


class PompeSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Pompe
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'nom', 'type', 'diametre', 'puissance', 'debit',
            'symbole', 'observation', 'last_intervention_date'
        )


class VanneSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Vanne
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'marque', 'type', 'diametre', 'materiau',
            'pression', 'symbole', 'observation'
        )


class ClapetSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Clapet
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'marque', 'type', 'diametre', 'materiau',
            'pression', 'symbole', 'observation'
        )


class CanalisationSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Canalisation
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'marque', 'type', 'diametre', 'materiau',
            'pression', 'symbole', 'observation'
        )


class AspersionSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Aspersion
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'marque', 'type', 'diametre', 'materiau',
            'pression', 'symbole', 'observation'
        )


class GoutteSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Goutte
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'type', 'diametre', 'materiau', 'pression',
            'symbole', 'observation'
        )


class BallonSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Ballon
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'etat',
            'marque', 'pression', 'volume', 'materiau',
            'observation'
        )
