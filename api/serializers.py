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
    centroid = GeometryField()

    class Meta:
        model = Site
        geo_field = "geometrie_emprise"
        fields = (
            'id', 'nom_site', 'adresse', 'superficie_totale', 'code_site',
            'date_debut_contrat', 'date_fin_contrat', 'actif', 'centroid'
        )


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
            'nom', 'famille', 'taille', 'symbole', 'observation', 'last_intervention_date'
        )


class GazonSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Gazon
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'area_sqm', 'observation', 'last_intervention_date'
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
            'nom', 'famille', 'taille', 'symbole', 'observation', 'last_intervention_date'
        )


class ArbusteSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Arbuste
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'densite', 'symbole', 'observation', 'last_intervention_date'
        )


class VivaceSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Vivace
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'densite', 'observation', 'last_intervention_date'
        )


class CactusSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Cactus
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'densite', 'observation', 'last_intervention_date'
        )


class GramineeSerializer(GeoFeatureModelSerializer):
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    sous_site_nom = serializers.SerializerMethodField()
    geometry = GeometryField()

    def get_sous_site_nom(self, obj):
        return obj.sous_site.nom if obj.sous_site else None

    class Meta:
        model = Graminee
        geo_field = "geometry"
        fields = (
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'densite', 'symbole', 'observation', 'last_intervention_date'
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
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'profondeur', 'diametre', 'niveau_statique',
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
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'type', 'diametre', 'puissance', 'debit',
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
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'marque', 'type', 'diametre', 'materiau',
            'pression', 'symbole', 'observation', 'last_intervention_date'
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
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'marque', 'type', 'diametre', 'materiau',
            'pression', 'symbole', 'observation', 'last_intervention_date'
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
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'marque', 'type', 'diametre', 'materiau',
            'pression', 'symbole', 'observation', 'last_intervention_date'
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
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'marque', 'type', 'diametre', 'materiau',
            'pression', 'symbole', 'observation', 'last_intervention_date'
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
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'type', 'diametre', 'materiau', 'pression',
            'symbole', 'observation', 'last_intervention_date'
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
            'id', 'site', 'site_nom', 'sous_site', 'sous_site_nom',
            'nom', 'famille', 'marque', 'pression', 'volume', 'materiau',
            'observation', 'last_intervention_date'
        )
