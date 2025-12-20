from rest_framework import serializers
from rest_framework_gis.fields import GeometryField
from .models import TypeReclamation, Urgence, Reclamation, HistoriqueReclamation, SatisfactionClient
from api_suivi_taches.serializers import PhotoSerializer, PhotoCreateSerializer
from api_suivi_taches.models import Photo

# ==============================================================================
# SERIALIZERS - REFERENTIELS
# ==============================================================================

class TypeReclamationSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeReclamation
        fields = ['id', 'nom_reclamation', 'code_reclamation', 'symbole', 'categorie', 'actif']


class UrgenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Urgence
        fields = ['id', 'niveau_urgence', 'couleur', 'delai_max_traitement', 'ordre']


# ==============================================================================
# SERIALIZERS - RECLAMATION
# ==============================================================================

class ReclamationListSerializer(serializers.ModelSerializer):
    """Pour l'affichage en liste (performances)."""
    type_reclamation_nom = serializers.CharField(source='type_reclamation.nom_reclamation', read_only=True)
    urgence_niveau = serializers.CharField(source='urgence.niveau_urgence', read_only=True)
    urgence_couleur = serializers.CharField(source='urgence.couleur', read_only=True)
    site_nom = serializers.CharField(source='site.nom_site', read_only=True)
    zone_nom = serializers.CharField(source='zone.nom', read_only=True, allow_null=True)
    createur_nom = serializers.SerializerMethodField()

    class Meta:
        model = Reclamation
        fields = [
            'id',
            'numero_reclamation',
            'type_reclamation', 'type_reclamation_nom',
            'urgence', 'urgence_niveau', 'urgence_couleur',
            'date_creation',
            'date_constatation',
            'statut',
            'site', 'site_nom',
            'zone', 'zone_nom',
            'date_cloture_prevue',
            'date_cloture_reelle',
            'description',
            'createur', 'createur_nom'
        ]

    def get_createur_nom(self, obj):
        if obj.createur:
            return f"{obj.createur.prenom} {obj.createur.nom}".strip() or obj.createur.email
        return None



# ==============================================================================
# SERIALIZER - HISTORIQUE
# ==============================================================================

class HistoriqueReclamationSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = HistoriqueReclamation
        fields = ['id', 'statut_precedent', 'statut_nouveau', 'date_changement', 'auteur', 'auteur_nom', 'commentaire']

    def get_auteur_nom(self, obj):
        if obj.auteur:
            return f"{obj.auteur.prenom} {obj.auteur.nom}".strip() or obj.auteur.email
        return "Système"





class ReclamationDetailSerializer(serializers.ModelSerializer):
    """Pour l'affichage détaillé."""
    type_reclamation_detail = TypeReclamationSerializer(source='type_reclamation', read_only=True)
    urgence_detail = UrgenceSerializer(source='urgence', read_only=True)
    type_reclamation_nom = serializers.CharField(source='type_reclamation.nom_reclamation', read_only=True)
    urgence_niveau = serializers.CharField(source='urgence.niveau_urgence', read_only=True)
    urgence_couleur = serializers.CharField(source='urgence.couleur', read_only=True)
    site_nom = serializers.CharField(source='site.nom_site', read_only=True, allow_null=True)
    zone_nom = serializers.CharField(source='zone.nom', read_only=True, allow_null=True)
    equipe_nom = serializers.CharField(source='equipe_affectee.nom_equipe', read_only=True, allow_null=True)
    photos = PhotoSerializer(many=True, read_only=True)
    photos_taches = serializers.SerializerMethodField()
    taches_liees_details = serializers.SerializerMethodField()
    historique = HistoriqueReclamationSerializer(many=True, read_only=True)
    satisfaction = serializers.SerializerMethodField()

    class Meta:
        model = Reclamation
        fields = '__all__'

    def get_taches_liees_details(self, obj):
        """Retourne les infos de base des tâches liées."""
        taches = obj.taches_correctives.filter(deleted_at__isnull=True)
        return [{
            'id': t.id,
            'type_tache': t.id_type_tache.nom_tache,
            'statut': t.statut,
            'date_debut': t.date_debut_planifiee,
            'equipe': t.id_equipe.nom_equipe if t.id_equipe else (t.equipes.first().nom_equipe if t.equipes.exists() else None)
        } for t in taches]

    def get_photos_taches(self, obj):
        """Retourne les photos liées aux tâches de cette réclamation."""
        from api_suivi_taches.models import Photo
        photos = Photo.objects.filter(tache__reclamation=obj)
        # On utilise PhotoListSerializer pour avoir un format plus léger si besoin
        # ou PhotoSerializer pour avoir l'URL complète
        return PhotoSerializer(photos, many=True, context=self.context).data

    def get_createur_nom(self, obj):
        if obj.createur:
            return f"{obj.createur.prenom} {obj.createur.nom}".strip() or obj.createur.email
        return None

    def get_satisfaction(self, obj):
        """Retourne les données de satisfaction si elles existent."""
        try:
            satisfaction = obj.satisfaction
            return {
                'id': satisfaction.id,
                'note': satisfaction.note,
                'commentaire': satisfaction.commentaire,
                'date_evaluation': satisfaction.date_evaluation
            }
        except SatisfactionClient.DoesNotExist:
            return None


class PhotoNestedSerializer(serializers.ModelSerializer):
    """Serializer pour les photos créées de manière imbriquée (sans validation FK stricte)."""
    class Meta:
        model = Photo
        fields = ['fichier', 'type_photo', 'legende']

class ReclamationCreateSerializer(serializers.ModelSerializer):
    """Pour la création."""
    photos = PhotoNestedSerializer(many=True, required=False)
    # Client et createur sont optionnels et assignés dans la vue
    client = serializers.PrimaryKeyRelatedField(read_only=True, required=False)
    createur = serializers.PrimaryKeyRelatedField(read_only=True, required=False)
    # Geometry field for GeoJSON format
    localisation = GeometryField(required=False, allow_null=True)

    class Meta:
        model = Reclamation
        fields = [
            'type_reclamation',
            'urgence',
            'site',
            'zone',
            'localisation',
            'description',
            'date_constatation',
            'photos',
            'client',
            'createur'
        ]
        
    def create(self, validated_data):
        photos_data = validated_data.pop('photos', [])
        reclamation = Reclamation.objects.create(**validated_data)
        
        # Gestion des photos si envoyées
        for photo_data in photos_data:
            Photo.objects.create(reclamation=reclamation, **photo_data)
            
        return reclamation

    def update(self, instance, validated_data):
        """Mettre à jour la réclamation et ajouter de nouvelles photos."""
        photos_data = validated_data.pop('photos', [])
        
        # Mise à jour des champs standards
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Ajout des nouvelles photos
        for photo_data in photos_data:
            Photo.objects.create(reclamation=instance, **photo_data)
            
        return instance


# ==============================================================================
# SERIALIZER - SATISFACTION CLIENT (User 6.6.13)
# ==============================================================================

class SatisfactionClientSerializer(serializers.ModelSerializer):
    reclamation_numero = serializers.CharField(source='reclamation.numero_reclamation', read_only=True)
    
    class Meta:
        model = SatisfactionClient
        fields = ['id', 'reclamation', 'reclamation_numero', 'note', 'commentaire', 'date_evaluation']
        read_only_fields = ['id', 'date_evaluation']

