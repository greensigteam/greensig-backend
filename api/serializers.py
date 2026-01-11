# api/serializers.py
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework_gis.fields import GeometryField
from rest_framework import serializers
from .models import (
    Site, SousSite, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon,
    Notification
)


# ==============================================================================
# SERIALIZERS POUR LA HIÉRARCHIE SPATIALE
# ==============================================================================

class SiteSerializer(GeoFeatureModelSerializer):
    geometrie_emprise = GeometryField()
    centroid = GeometryField(read_only=True)  # Auto-calculated from geometrie_emprise
    code_site = serializers.CharField(read_only=True)  # Auto-generated
    client_nom = serializers.SerializerMethodField()
    structure_client_nom = serializers.SerializerMethodField()
    superviseur_nom = serializers.SerializerMethodField()
    superficie_calculee = serializers.SerializerMethodField()
    superviseur_id = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Site
        geo_field = "geometrie_emprise"
        fields = (
            'id', 'nom_site', 'adresse', 'superficie_totale', 'superficie_calculee', 'code_site',
            'client', 'client_nom',
            'structure_client', 'structure_client_nom',
            'superviseur', 'superviseur_id', 'superviseur_nom',
            'date_debut_contrat', 'date_fin_contrat', 'actif', 'centroid'
        )

    def get_superviseur_id(self, obj):
        """Return superviseur ID (utilisateur PK)"""
        return obj.superviseur_id if obj.superviseur else None

    def get_client_nom(self, obj):
        """Return client name or None if no client assigned (legacy)"""
        if obj.structure_client:
            return obj.structure_client.nom
        return obj.client.nom_structure if obj.client else None

    def get_structure_client_nom(self, obj):
        """Return structure client name or None if no structure assigned"""
        return obj.structure_client.nom if obj.structure_client else None

    def get_superviseur_nom(self, obj):
        """Return superviseur full name or None if no superviseur assigned"""
        if obj.superviseur and obj.superviseur.utilisateur:
            user = obj.superviseur.utilisateur
            return f"{user.prenom} {user.nom}" if user.prenom and user.nom else user.email
        return None

    def get_superficie_calculee(self, obj):
        """Calculate surface area from geometrie_emprise polygon (in square meters)"""
        if not obj.geometrie_emprise:
            return None
        try:
            # Transform to projected CRS for accurate area calculation
            from django.contrib.gis.geos import GEOSGeometry
            geom = obj.geometrie_emprise
            # Transform from WGS84 (4326) to Web Mercator (3857) for area calculation
            geom_projected = geom.transform(3857, clone=True)
            area_sqm = geom_projected.area  # Area in square meters
            return round(area_sqm, 2)
        except Exception:
            return None

    def to_internal_value(self, data):
        """
        Handle superviseur field: accept user ID and convert to Superviseur.
        Creates Superviseur record if user has SUPERVISEUR role but no record exists.
        """
        # Get superviseur from properties (GeoJSON format)
        superviseur_id = None
        if 'properties' in data and 'superviseur' in data['properties']:
            superviseur_id = data['properties'].get('superviseur')
        elif 'superviseur' in data:
            superviseur_id = data.get('superviseur')

        # Process superviseur if provided
        if superviseur_id is not None:
            from api_users.models import Utilisateur, Superviseur, UtilisateurRole
            from django.utils import timezone

            if superviseur_id == '' or superviseur_id is None:
                # Allow setting superviseur to null
                if 'properties' in data:
                    data['properties']['superviseur'] = None
                else:
                    data['superviseur'] = None
            else:
                try:
                    superviseur_id = int(superviseur_id)

                    # Check if Superviseur record exists
                    try:
                        superviseur = Superviseur.objects.get(pk=superviseur_id)
                    except Superviseur.DoesNotExist:
                        # Check if user exists and has SUPERVISEUR role
                        try:
                            user = Utilisateur.objects.get(pk=superviseur_id)
                        except Utilisateur.DoesNotExist:
                            raise serializers.ValidationError({
                                'superviseur': f"Utilisateur {superviseur_id} n'existe pas."
                            })

                        # Check if user has SUPERVISEUR role
                        has_role = UtilisateurRole.objects.filter(
                            utilisateur=user,
                            role__nom_role='SUPERVISEUR'
                        ).exists()

                        if not has_role:
                            raise serializers.ValidationError({
                                'superviseur': f"L'utilisateur {user.email} n'a pas le rôle SUPERVISEUR."
                            })

                        # Create Superviseur record for this user
                        superviseur = Superviseur.objects.create(
                            utilisateur=user,
                            matricule=f"SUP-{user.id}",
                            date_prise_fonction=timezone.now().date()
                        )

                    # Update data with valid superviseur PK
                    if 'properties' in data:
                        data['properties']['superviseur'] = superviseur.pk
                    else:
                        data['superviseur'] = superviseur.pk

                except ValueError:
                    raise serializers.ValidationError({
                        'superviseur': "L'ID du superviseur doit être un entier."
                    })

        return super().to_internal_value(data)

    def to_representation(self, instance):
        """Override to return superviseur as user ID"""
        ret = super().to_representation(instance)
        # Return superviseur as the user ID (Superviseur PK)
        if instance.superviseur:
            ret['superviseur'] = instance.superviseur_id
        else:
            ret['superviseur'] = None
        return ret


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
        """
        Calculate area in square meters using PostGIS ST_Area with geography.
        OPTIMISÉ: Utilise l'annotation si disponible, sinon calcule à la volée.
        """
        # Si l'annotation existe (pré-calculée par la view), l'utiliser
        if hasattr(obj, '_superficie_annotee') and obj._superficie_annotee is not None:
            return round(obj._superficie_annotee, 2)

        # Fallback: calcul à la volée (pour compatibilité)
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
        """
        Calculate area in square meters using PostGIS ST_Area with geography.
        OPTIMISÉ: Utilise l'annotation si disponible, sinon calcule à la volée.
        """
        # Si l'annotation existe (pré-calculée par la view), l'utiliser
        if hasattr(obj, '_superficie_annotee') and obj._superficie_annotee is not None:
            return round(obj._superficie_annotee, 2)

        # Fallback: calcul à la volée (pour compatibilité)
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
        """
        Calculate area in square meters using PostGIS ST_Area with geography.
        OPTIMISÉ: Utilise l'annotation si disponible, sinon calcule à la volée.
        """
        # Si l'annotation existe (pré-calculée par la view), l'utiliser
        if hasattr(obj, '_superficie_annotee') and obj._superficie_annotee is not None:
            return round(obj._superficie_annotee, 2)

        # Fallback: calcul à la volée (pour compatibilité)
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
        """
        Calculate area in square meters using PostGIS ST_Area with geography.
        OPTIMISÉ: Utilise l'annotation si disponible, sinon calcule à la volée.
        """
        # Si l'annotation existe (pré-calculée par la view), l'utiliser
        if hasattr(obj, '_superficie_annotee') and obj._superficie_annotee is not None:
            return round(obj._superficie_annotee, 2)

        # Fallback: calcul à la volée (pour compatibilité)
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
        """
        Calculate area in square meters using PostGIS ST_Area with geography.
        OPTIMISÉ: Utilise l'annotation si disponible, sinon calcule à la volée.
        """
        # Si l'annotation existe (pré-calculée par la view), l'utiliser
        if hasattr(obj, '_superficie_annotee') and obj._superficie_annotee is not None:
            return round(obj._superficie_annotee, 2)

        # Fallback: calcul à la volée (pour compatibilité)
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


# ==============================================================================
# SERIALIZERS POUR LES NOTIFICATIONS
# ==============================================================================

class NotificationSerializer(serializers.ModelSerializer):
    """Serializer pour les notifications temps reel."""

    # Alias 'type' pour compatibilite frontend (attend 'type' au lieu de 'type_notification')
    type = serializers.CharField(source='type_notification', read_only=True)
    # Retourner acteur comme objet avec id et nom (format attendu par frontend)
    acteur = serializers.SerializerMethodField()
    type_label = serializers.CharField(source='get_type_notification_display', read_only=True)
    priorite_label = serializers.CharField(source='get_priorite_display', read_only=True)

    class Meta:
        model = Notification
        fields = (
            'id', 'type', 'type_notification', 'type_label', 'titre', 'message',
            'priorite', 'priorite_label', 'data', 'lu', 'date_lecture',
            'acteur', 'created_at'
        )
        read_only_fields = fields

    def get_acteur(self, obj):
        """Retourne acteur comme objet {id, nom} pour le frontend."""
        if obj.acteur:
            nom = f"{obj.acteur.prenom} {obj.acteur.nom}".strip() or obj.acteur.email
            return {'id': obj.acteur.id, 'nom': nom}
        return None


class AdminNotificationSerializer(NotificationSerializer):
    """
    Serializer pour les admins - inclut les infos du destinataire.
    Permet aux admins de voir toutes les notifications du systeme.
    """
    destinataire_id = serializers.IntegerField(source='destinataire.id', read_only=True)
    destinataire_nom = serializers.SerializerMethodField()
    destinataire_email = serializers.EmailField(source='destinataire.email', read_only=True)
    destinataire_role = serializers.SerializerMethodField()

    class Meta(NotificationSerializer.Meta):
        fields = NotificationSerializer.Meta.fields + (
            'destinataire_id', 'destinataire_nom', 'destinataire_email', 'destinataire_role'
        )

    def get_destinataire_nom(self, obj):
        if obj.destinataire:
            return f"{obj.destinataire.prenom} {obj.destinataire.nom}".strip() or obj.destinataire.email
        return None

    def get_destinataire_role(self, obj):
        """Retourne le role principal du destinataire."""
        if not obj.destinataire:
            return None
        # Verifier le type de profil
        if hasattr(obj.destinataire, 'superviseur_profile'):
            return 'SUPERVISEUR'
        if hasattr(obj.destinataire, 'client_profile'):
            return 'CLIENT'
        # Verifier via UtilisateurRole
        role = obj.destinataire.roles_utilisateur.first()
        if role:
            return role.role.nom_role
        return 'ADMIN'
