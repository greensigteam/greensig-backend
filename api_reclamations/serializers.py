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
    localisation = GeometryField(read_only=True, allow_null=True)

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
            'createur', 'createur_nom',
            'localisation'
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
    createur_nom = serializers.SerializerMethodField()
    photos = PhotoSerializer(many=True, read_only=True)
    photos_taches = serializers.SerializerMethodField()
    taches_liees_details = serializers.SerializerMethodField()
    historique = HistoriqueReclamationSerializer(many=True, read_only=True)
    satisfaction = serializers.SerializerMethodField()
    localisation = GeometryField(read_only=True, allow_null=True)

    class Meta:
        model = Reclamation
        fields = '__all__'

    def get_taches_liees_details(self, obj):
        """Retourne les infos de base des tâches liées.

        Note: Utilise le prefetch 'taches_correctives' avec select_related pour éviter N+1.
        Le prefetch filtre déjà sur deleted_at__isnull=True dans la view.
        """
        # Utilise le cache prefetch si disponible, sinon fallback
        if hasattr(obj, '_prefetched_objects_cache') and 'taches_correctives' in obj._prefetched_objects_cache:
            taches = obj._prefetched_objects_cache['taches_correctives']
        else:
            # Fallback avec optimisation
            taches = obj.taches_correctives.filter(deleted_at__isnull=True).select_related(
                'id_type_tache', 'id_equipe'
            ).prefetch_related('equipes')

        result = []
        for t in taches:
            # Utilise les relations prefetchées
            equipe_nom = None
            if t.id_equipe:
                equipe_nom = t.id_equipe.nom_equipe
            elif hasattr(t, '_prefetched_objects_cache') and 'equipes' in t._prefetched_objects_cache:
                equipes_list = t._prefetched_objects_cache['equipes']
                if equipes_list:
                    equipe_nom = equipes_list[0].nom_equipe
            else:
                first_equipe = t.equipes.first()
                if first_equipe:
                    equipe_nom = first_equipe.nom_equipe

            result.append({
                'id': t.id,
                'type_tache': t.id_type_tache.nom_tache if t.id_type_tache else None,
                'statut': t.statut,
                'date_debut': t.date_debut_planifiee,
                'equipe': equipe_nom
            })
        return result

    def get_photos_taches(self, obj):
        """Retourne les photos liées aux tâches de cette réclamation.

        Optimisé: récupère les IDs des tâches préchargées pour limiter la requête.
        """
        from api_suivi_taches.models import Photo

        # Récupère les IDs des tâches depuis le cache prefetch si disponible
        if hasattr(obj, '_prefetched_objects_cache') and 'taches_correctives' in obj._prefetched_objects_cache:
            tache_ids = [t.id for t in obj._prefetched_objects_cache['taches_correctives']]
            if not tache_ids:
                return []
            photos = Photo.objects.filter(tache_id__in=tache_ids).select_related('tache')
        else:
            photos = Photo.objects.filter(tache__reclamation=obj).select_related('tache')

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
    # Date de constatation optionnelle (remplie automatiquement si non fournie)
    date_constatation = serializers.DateTimeField(required=False)

    class Meta:
        model = Reclamation
        fields = [
            'id',
            'numero_reclamation',
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
        read_only_fields = ['id', 'numero_reclamation']

    def validate(self, attrs):
        """
        Validation: si une localisation est fournie sans site,
        on vérifie qu'un site peut être détecté automatiquement.
        Validation de la date de constatation (horodatage).
        """
        from api.models import Site, SousSite
        from django.utils import timezone

        localisation = attrs.get('localisation')
        site = attrs.get('site')

        # Si on a une localisation mais pas de site explicite
        if localisation and not site:
            # Chercher un SousSite qui intersecte
            found_zone = SousSite.objects.filter(geometrie__intersects=localisation).select_related('site').first()
            if found_zone and found_zone.site:
                # Un site sera détecté automatiquement, OK
                pass
            else:
                # Chercher un Site qui intersecte
                found_site = Site.objects.filter(geometrie_emprise__intersects=localisation).first()
                if not found_site:
                    raise serializers.ValidationError({
                        "localisation": "La zone indiquée ne correspond à aucun site connu. Veuillez dessiner la zone à l'intérieur d'un site."
                    })

        # Validation de la date de constatation (horodatage)
        date_constatation = attrs.get('date_constatation')
        if date_constatation:
            now = timezone.now()

            # La date de constatation ne peut pas être dans le futur
            if date_constatation > now:
                raise serializers.ValidationError({
                    "date_constatation": "La date de constatation ne peut pas être dans le futur."
                })

            # La date de constatation ne peut pas être trop ancienne (plus de 90 jours)
            days_ago = (now - date_constatation).days
            if days_ago > 90:
                raise serializers.ValidationError({
                    "date_constatation": f"La date de constatation ne peut pas dépasser 90 jours ({days_ago} jours). Veuillez contacter un administrateur pour les cas exceptionnels."
                })

        return attrs

    def create(self, validated_data):
        current_user = validated_data.pop('_current_user', None)
        photos_data = validated_data.pop('photos', [])

        # Créer l'instance sans sauvegarder
        reclamation = Reclamation(**validated_data)
        if current_user:
            reclamation._current_user = current_user

        # Appeler la validation complète du modèle (inclut clean())
        reclamation.full_clean()

        # Sauvegarder après validation
        reclamation.save()

        # Gestion des photos si envoyées
        for photo_data in photos_data:
            Photo.objects.create(reclamation=reclamation, **photo_data)

        return reclamation

    def update(self, instance, validated_data):
        """Mettre à jour la réclamation et ajouter de nouvelles photos."""
        current_user = validated_data.pop('_current_user', None)
        if current_user:
            instance._current_user = current_user
            
        photos_data = validated_data.pop('photos', [])

        # Mise à jour des champs standards
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Appeler la validation complète du modèle (inclut clean())
        instance.full_clean()

        # Sauvegarder après validation
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

