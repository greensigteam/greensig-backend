from rest_framework import serializers
from .models import TypeTache, Tache, ParticipationTache, RatioProductivite
from api_users.serializers import ClientSerializer, EquipeListSerializer, OperateurListSerializer
from api_users.models import Equipe
from api.models import Objet

class TypeTacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeTache
        fields = '__all__'


class RatioProductiviteSerializer(serializers.ModelSerializer):
    """Serializer pour les ratios de productivité"""
    type_tache_nom = serializers.CharField(source='id_type_tache.nom_tache', read_only=True)

    class Meta:
        model = RatioProductivite
        fields = ['id', 'id_type_tache', 'type_tache_nom', 'type_objet',
                  'unite_mesure', 'ratio', 'description', 'actif']

class ObjetSimpleSerializer(serializers.ModelSerializer):
    nom_type = serializers.CharField(source='get_nom_type', read_only=True)
    display = serializers.CharField(source='__str__', read_only=True)

    class Meta:
        model = Objet
        fields = ['id', 'site', 'sous_site', 'nom_type', 'display']

class ParticipationTacheSerializer(serializers.ModelSerializer):
    operateur_nom = serializers.CharField(source='id_operateur.utilisateur.get_full_name', read_only=True)
    
    class Meta:
        model = ParticipationTache
        fields = ['id', 'id_tache', 'id_operateur', 'role', 'heures_travaillees', 'realisation', 'operateur_nom']
        read_only_fields = ['id', 'operateur_nom']

class TacheSerializer(serializers.ModelSerializer):
    """Serializer COMPLET pour GET (lecture)"""
    client_detail = ClientSerializer(source='id_client', read_only=True)
    type_tache_detail = TypeTacheSerializer(source='id_type_tache', read_only=True)
    # Legacy single team (for backwards compatibility)
    equipe_detail = EquipeListSerializer(source='id_equipe', read_only=True)
    # Multi-teams (US-PLAN-013)
    equipes_detail = EquipeListSerializer(source='equipes', many=True, read_only=True)
    participations_detail = ParticipationTacheSerializer(source='participations', many=True, read_only=True)
    objets_detail = ObjetSimpleSerializer(source='objets', many=True, read_only=True)
    reclamation_numero = serializers.CharField(source='reclamation.numero_reclamation', read_only=True, allow_null=True)

    class Meta:
        model = Tache
        fields = '__all__'

class TacheCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour CREATE/UPDATE"""
    # Multi-teams write field (US-PLAN-013)
    equipes_ids = serializers.PrimaryKeyRelatedField(
        queryset=Equipe.objects.all(),
        many=True,
        source='equipes',
        required=False,
        write_only=True
    )

    class Meta:
        model = Tache
        fields = '__all__'
        read_only_fields = ['deleted_at']

    def validate(self, data):
        start = data.get('date_debut_planifiee')
        end = data.get('date_fin_planifiee')

        # Validation uniquement si les deux dates sont présentes (cas création ou update complet)
        if start and end:
            if end < start:
                raise serializers.ValidationError({"date_fin_planifiee": "La date de fin ne peut pas être antérieure à la date de début."})

        # Si une charge est fournie manuellement, activer le flag charge_manuelle
        if 'charge_estimee_heures' in data and data['charge_estimee_heures'] is not None:
            data['charge_manuelle'] = True

        # Validation: tous les objets doivent appartenir au même site
        objets = data.get('objets')
        if objets and len(objets) > 1:
            site_ids = set(obj.site_id for obj in objets)
            if len(site_ids) > 1:
                raise serializers.ValidationError({
                    "objets": "Tous les objets doivent appartenir au même site. "
                              "Les objets sélectionnés appartiennent à plusieurs sites différents."
                })

        # Validation: le type de tâche doit être applicable à tous les types d'objets sélectionnés
        type_tache = data.get('id_type_tache')
        if type_tache and objets:
            # Récupérer les types d'objets uniques parmi les objets sélectionnés
            types_objets = set()
            for obj in objets:
                # obj est une instance d'Objet, on récupère le type réel
                type_reel = obj.get_nom_type()
                if type_reel:
                    types_objets.add(type_reel)

            # Vérifier que pour chaque type d'objet, un ratio existe
            types_non_applicables = []
            for type_objet in types_objets:
                ratio_exists = RatioProductivite.objects.filter(
                    id_type_tache=type_tache,
                    type_objet=type_objet,
                    actif=True
                ).exists()
                if not ratio_exists:
                    types_non_applicables.append(type_objet)

            if types_non_applicables:
                raise serializers.ValidationError({
                    "id_type_tache": f"Le type de tâche '{type_tache.nom_tache}' n'est pas applicable aux types d'objets suivants: {', '.join(types_non_applicables)}. "
                                     "Veuillez sélectionner un type de tâche compatible avec tous les objets."
                })

        return data

    def create(self, validated_data):
        # Extract M2M equipes if provided
        equipes = validated_data.pop('equipes', None)
        instance = super().create(validated_data)
        if equipes is not None:
            instance.equipes.set(equipes)
        return instance

    def update(self, instance, validated_data):
        # Extract M2M equipes if provided
        equipes = validated_data.pop('equipes', None)
        instance = super().update(instance, validated_data)
        if equipes is not None:
            instance.equipes.set(equipes)
        return instance
