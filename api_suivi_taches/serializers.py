"""
Serializers pour le module Suivi des Tâches
"""
from rest_framework import serializers
from .models import (
    Produit,
    ProduitMatiereActive,
    DoseProduit,
    ConsommationProduit,
    Photo,
    Fertilisant,
    RavageurMaladie
)


# ==============================================================================
# SERIALIZERS - PRODUIT
# ==============================================================================

class ProduitMatiereActiveSerializer(serializers.ModelSerializer):
    """Serializer pour les matières actives d'un produit."""
    
    class Meta:
        model = ProduitMatiereActive
        fields = [
            'id',
            'matiere_active',
            'teneur_valeur',
            'teneur_unite',
            'ordre'
        ]


class DoseProduitSerializer(serializers.ModelSerializer):
    """Serializer pour les doses d'un produit."""
    
    class Meta:
        model = DoseProduit
        fields = [
            'id',
            'dose_valeur',
            'dose_unite_produit',
            'dose_unite_support',
            'contexte'
        ]


class ProduitListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des produits (vue simplifiée)."""
    
    est_valide = serializers.ReadOnlyField()
    
    class Meta:
        model = Produit
        fields = [
            'id',
            'nom_produit',
            'numero_homologation',
            'date_validite',
            'cible',
            'actif',
            'est_valide'
        ]


class ProduitDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un produit avec matières actives et doses."""
    
    matieres_actives = ProduitMatiereActiveSerializer(many=True, read_only=True)
    doses = DoseProduitSerializer(many=True, read_only=True)
    est_valide = serializers.ReadOnlyField()
    
    class Meta:
        model = Produit
        fields = [
            'id',
            'nom_produit',
            'numero_homologation',
            'date_validite',
            'cible',
            'description',
            'actif',
            'date_creation',
            'est_valide',
            'matieres_actives',
            'doses'
        ]


class ProduitCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un produit."""
    
    class Meta:
        model = Produit
        fields = [
            'nom_produit',
            'numero_homologation',
            'date_validite',
            'cible',
            'description',
            'actif'
        ]


# ==============================================================================
# SERIALIZERS - CONSOMMATION PRODUIT
# ==============================================================================

class ConsommationProduitSerializer(serializers.ModelSerializer):
    """Serializer pour la consommation de produits."""
    
    produit_detail = ProduitListSerializer(source='produit', read_only=True)
    produit_nom = serializers.CharField(source='produit.nom_produit', read_only=True)
    
    class Meta:
        model = ConsommationProduit
        fields = [
            'id',
            'tache',
            'produit',
            'produit_detail',
            'produit_nom',
            'quantite_utilisee',
            'unite',
            'date_utilisation',
            'commentaire'
        ]
        read_only_fields = ['date_utilisation']


class ConsommationProduitCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une consommation de produit."""
    
    class Meta:
        model = ConsommationProduit
        fields = [
            'tache',
            'produit',
            'quantite_utilisee',
            'unite',
            'commentaire'
        ]
    
    def validate_quantite_utilisee(self, value):
        """Valide que la quantité est positive."""
        if value <= 0:
            raise serializers.ValidationError("La quantité doit être supérieure à 0.")
        return value


# ==============================================================================
# SERIALIZERS - PHOTO
# ==============================================================================

class PhotoSerializer(serializers.ModelSerializer):
    """Serializer pour les photos."""
    
    type_photo_display = serializers.CharField(source='get_type_photo_display', read_only=True)
    url_fichier = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            'id',
            'fichier',
            'url_fichier',
            'type_photo',
            'type_photo_display',
            'date_prise',
            'tache',
            'objet',
            'reclamation',
            'legende',
            'latitude',
            'longitude'
        ]
        read_only_fields = ['date_prise']
    
    def get_url_fichier(self, obj):
        """Retourne l'URL complète du fichier image."""
        if obj.fichier:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fichier.url)
            return obj.fichier.url
        return None



class PhotoCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer une photo."""

    class Meta:
        model = Photo
        fields = [
            'fichier',
            'type_photo',
            'tache',
            'objet',
            'reclamation',
            'legende',
            'latitude',
            'longitude'
        ]
        extra_kwargs = {
            'tache': {'required': False, 'allow_null': True},
            'objet': {'required': False, 'allow_null': True},
            'reclamation': {'required': False, 'allow_null': True},
        }

    def to_internal_value(self, data):
        """Convertit les IDs string en int avant la validation des FK."""
        # ✅ FIX: Éviter .copy() sur un QueryDict (Multipart data) car il fait un deepcopy
        # qui échoue sur Windows avec des fichiers (BufferedRandom pickling error).
        if hasattr(data, 'dict'):
            mutable_data = data.dict()
        else:
            mutable_data = data.copy() if hasattr(data, 'copy') else dict(data)

        # Convertir les strings en int pour les FK
        for field in ['tache', 'objet', 'reclamation']:
            if field in mutable_data:
                value = mutable_data[field]
                if isinstance(value, str) and value.isdigit():
                    mutable_data[field] = int(value)
                elif value == '' or value is None:
                    mutable_data[field] = None

        return super().to_internal_value(mutable_data)

    def validate(self, data):
        """Valide qu'au moins une entité est liée."""
        if not any([data.get('tache'), data.get('objet'), data.get('reclamation')]):
            raise serializers.ValidationError(
                "Une photo doit être liée à au moins une entité (tâche, réclamation ou objet)."
            )
        return data


class PhotoListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des photos."""

    type_photo_display = serializers.CharField(source='get_type_photo_display', read_only=True)
    url_fichier = serializers.SerializerMethodField()

    class Meta:
        model = Photo
        fields = [
            'id',
            'url_fichier',
            'type_photo',
            'type_photo_display',
            'date_prise',
            'legende'
        ]

    def get_url_fichier(self, obj):
        """Retourne l'URL complète du fichier image."""
        if obj.fichier:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.fichier.url)
            return obj.fichier.url
        return None


# ==============================================================================
# SERIALIZERS - FERTILISANT
# ==============================================================================

class FertilisantListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des fertilisants."""

    type_fertilisant_display = serializers.CharField(
        source='get_type_fertilisant_display', read_only=True
    )
    format_fertilisant_display = serializers.CharField(
        source='get_format_fertilisant_display', read_only=True
    )

    class Meta:
        model = Fertilisant
        fields = [
            'id',
            'nom',
            'type_fertilisant',
            'type_fertilisant_display',
            'format_fertilisant',
            'format_fertilisant_display',
            'actif',
            'date_creation'
        ]


class FertilisantDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un fertilisant."""

    type_fertilisant_display = serializers.CharField(
        source='get_type_fertilisant_display', read_only=True
    )
    format_fertilisant_display = serializers.CharField(
        source='get_format_fertilisant_display', read_only=True
    )

    class Meta:
        model = Fertilisant
        fields = [
            'id',
            'nom',
            'type_fertilisant',
            'type_fertilisant_display',
            'format_fertilisant',
            'format_fertilisant_display',
            'description',
            'actif',
            'date_creation'
        ]


class FertilisantCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier un fertilisant."""

    class Meta:
        model = Fertilisant
        fields = [
            'nom',
            'type_fertilisant',
            'format_fertilisant',
            'description',
            'actif'
        ]


# ==============================================================================
# SERIALIZERS - RAVAGEUR / MALADIE
# ==============================================================================

class RavageurMaladieListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des ravageurs/maladies."""

    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True
    )
    produits_count = serializers.SerializerMethodField()

    class Meta:
        model = RavageurMaladie
        fields = [
            'id',
            'nom',
            'categorie',
            'categorie_display',
            'symptomes',
            'partie_atteinte',
            'produits_count',
            'actif',
            'date_creation'
        ]

    def get_produits_count(self, obj):
        """Retourne le nombre de produits recommandés."""
        return obj.produits_recommandes.count()


class RavageurMaladieDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un ravageur/maladie."""

    categorie_display = serializers.CharField(
        source='get_categorie_display', read_only=True
    )
    produits_recommandes = ProduitListSerializer(many=True, read_only=True)
    produits_recommandes_ids = serializers.PrimaryKeyRelatedField(
        queryset=Produit.objects.all(),
        many=True,
        write_only=True,
        source='produits_recommandes',
        required=False
    )

    class Meta:
        model = RavageurMaladie
        fields = [
            'id',
            'nom',
            'categorie',
            'categorie_display',
            'symptomes',
            'partie_atteinte',
            'produits_recommandes',
            'produits_recommandes_ids',
            'actif',
            'date_creation'
        ]


class RavageurMaladieCreateSerializer(serializers.ModelSerializer):
    """Serializer pour créer/modifier un ravageur/maladie."""

    produits_recommandes_ids = serializers.PrimaryKeyRelatedField(
        queryset=Produit.objects.all(),
        many=True,
        write_only=True,
        required=False
    )

    class Meta:
        model = RavageurMaladie
        fields = [
            'nom',
            'categorie',
            'symptomes',
            'partie_atteinte',
            'produits_recommandes_ids',
            'actif'
        ]

    def create(self, validated_data):
        """Crée un ravageur/maladie avec les produits recommandés."""
        produits = validated_data.pop('produits_recommandes_ids', [])
        instance = RavageurMaladie.objects.create(**validated_data)
        if produits:
            instance.produits_recommandes.set(produits)
        return instance

    def update(self, instance, validated_data):
        """Met à jour un ravageur/maladie avec les produits recommandés."""
        produits = validated_data.pop('produits_recommandes_ids', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if produits is not None:
            instance.produits_recommandes.set(produits)
        return instance
