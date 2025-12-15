from rest_framework import serializers
from .models import TypeTache, Tache, ParticipationTache
from api_users.serializers import ClientSerializer, EquipeListSerializer, OperateurListSerializer
from api.models import Objet

class TypeTacheSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeTache
        fields = '__all__'

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
    equipe_detail = EquipeListSerializer(source='id_equipe', read_only=True)
    participations_detail = ParticipationTacheSerializer(source='participations', many=True, read_only=True)
    objets_detail = ObjetSimpleSerializer(source='objets', many=True, read_only=True)
    
    class Meta:
        model = Tache
        fields = '__all__'

class TacheCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour CREATE/UPDATE"""
    
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
        
        return data
