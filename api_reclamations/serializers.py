from rest_framework import serializers
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

    class Meta:
        model = Reclamation
        fields = [
            'id', 
            'numero_reclamation', 
            'type_reclamation', 'type_reclamation_nom',
            'urgence', 'urgence_niveau', 'urgence_couleur',
            'date_creation', 
            'statut', 
            'site', 'site_nom',
            'zone', 'zone_nom',
            'date_cloture_prevue',
            'date_cloture_reelle',
            'description'
        ]



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
    historique = HistoriqueReclamationSerializer(many=True, read_only=True)
    
    class Meta:
        model = Reclamation
        fields = '__all__'


class PhotoNestedSerializer(serializers.ModelSerializer):
    """Serializer pour les photos créées de manière imbriquée (sans validation FK stricte)."""
    class Meta:
        model = Photo
        fields = ['fichier', 'type_photo', 'legende']

class ReclamationCreateSerializer(serializers.ModelSerializer):
    """Pour la création."""
    photos = PhotoNestedSerializer(many=True, required=False)
    client = serializers.PrimaryKeyRelatedField(read_only=True, required=False)

    class Meta:
        model = Reclamation
        fields = [
            'type_reclamation', 
            'urgence', 
            'client', 
            'zone', 
            'localisation', 
            'description', 
            'date_constatation',
            'photos'
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
    
    def validate(self, data):
        # Vérifier qu'une seule évaluation par réclamation
        reclamation = data.get('reclamation')
        if reclamation and SatisfactionClient.objects.filter(reclamation=reclamation).exists():
            if not self.instance:  # Seulement en création
                raise serializers.ValidationError("Une évaluation existe déjà pour cette réclamation.")
        return data

