from rest_framework import serializers
from .models import TypeTache, Tache, ParticipationTache, RatioProductivite
from api_users.models import Equipe, Client, StructureClient
from api.models import Objet


class StructureClientLightSerializer(serializers.ModelSerializer):
    """Serializer allégé pour les structures client dans les tâches."""
    class Meta:
        model = StructureClient
        fields = ['id', 'nom', 'actif']


class ClientLightSerializer(serializers.ModelSerializer):
    """Serializer allégé pour les clients dans les tâches - évite les N+1."""
    nom = serializers.CharField(source='utilisateur.nom', read_only=True)
    prenom = serializers.CharField(source='utilisateur.prenom', read_only=True)
    email = serializers.EmailField(source='utilisateur.email', read_only=True)
    nom_complet = serializers.CharField(source='utilisateur.get_full_name', read_only=True)

    class Meta:
        model = Client
        fields = ['utilisateur', 'nom', 'prenom', 'email', 'nom_complet', 'nom_structure']

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

class ObjetMinimalSerializer(serializers.ModelSerializer):
    """⚡ Serializer MINIMAL pour les objets - SEULEMENT les infos essentielles pour l'affichage.

    Charge uniquement : ID + nom du site + type d'objet
    Pas de champs calculés, pas de __str__(), pas de géométrie.
    """
    site_nom = serializers.CharField(source='site.nom_site', read_only=True, allow_null=True)
    site_id = serializers.IntegerField(source='site.id', read_only=True, allow_null=True)

    class Meta:
        model = Objet
        fields = ['id', 'site_id', 'site_nom']


class ObjetSimpleSerializer(serializers.ModelSerializer):
    """Serializer ultra-léger pour les objets dans les tâches.

    N'utilise PAS get_nom_type() ou __str__() car ils causent des N+1.
    Utilise select_related/prefetch_related dans la vue pour éviter N+1.
    """
    site_nom = serializers.CharField(source='site.nom_site', read_only=True, allow_null=True)
    sous_site_nom = serializers.CharField(source='sous_site.nom', read_only=True, allow_null=True)
    nom_type = serializers.CharField(source='get_nom_type', read_only=True)
    display = serializers.CharField(source='__str__', read_only=True)
    # DISABLED: superficie_calculee causes N+1 queries (one SQL query per object)
    # To re-enable, use annotation in the queryset instead of SerializerMethodField
    # superficie_calculee = serializers.SerializerMethodField()

    # def get_superficie_calculee(self, obj):
    #     """Calculate area in square meters for surfacic objects (Polygon)."""
    #     from django.contrib.gis.geos import Polygon
    #
    #     # ✅ FIX: Check if object has geometry attribute (not all Objet subclasses have it)
    #     if not hasattr(obj, 'geometry'):
    #         return None
    #
    #     if obj.geometry and isinstance(obj.geometry, Polygon):
    #         # Use PostGIS ST_Area with geography for accurate results
    #         from django.db import connection
    #         try:
    #             with connection.cursor() as cursor:
    #                 cursor.execute(
    #                     "SELECT ST_Area(%s::geography)",
    #                     [obj.geometry.ewkt]
    #                 )
    #                 result = cursor.fetchone()
    #                 return round(result[0], 2) if result and result[0] else None
    #         except Exception:
    #             return None
    #     return None

    class Meta:
        model = Objet
        fields = ['id', 'site', 'site_nom', 'sous_site', 'sous_site_nom', 'nom_type', 'display']

class ParticipationTacheSerializer(serializers.ModelSerializer):
    operateur_nom = serializers.CharField(source='id_operateur.nom_complet', read_only=True)

    class Meta:
        model = ParticipationTache
        fields = ['id', 'id_tache', 'id_operateur', 'role', 'heures_travaillees', 'realisation', 'operateur_nom']
        read_only_fields = ['id', 'operateur_nom']


class EquipeMinimalSerializer(serializers.ModelSerializer):
    """⚡ Serializer MINIMAL pour les équipes - SEULEMENT ID + nom.

    Pas de chef d'équipe, pas de membres, pas de calculs.
    Utilisé pour l'affichage rapide dans la liste des tâches.
    """
    class Meta:
        model = Equipe
        fields = ['id', 'nom_equipe']


class EquipeLightSerializer(serializers.ModelSerializer):
    """Serializer allégé pour les équipes dans les tâches - évite les N+1 queries.

    Utilise les données prefetchées au lieu des properties coûteuses.
    """
    chef_equipe_nom = serializers.CharField(
        source='chef_equipe.nom_complet',
        read_only=True,
        allow_null=True
    )
    # Calcul du nombre de membres depuis les données prefetchées
    nombre_membres = serializers.SerializerMethodField()

    class Meta:
        model = Equipe
        fields = [
            'id', 'nom_equipe', 'chef_equipe', 'chef_equipe_nom',
            'actif', 'date_creation', 'nombre_membres'
        ]

    def get_nombre_membres(self, obj):
        """Compte les membres depuis les données prefetchées."""
        from api_users.models import StatutOperateur
        # Si les opérateurs sont prefetchés, on les compte en mémoire
        if hasattr(obj, '_prefetched_objects_cache') and 'operateurs' in obj._prefetched_objects_cache:
            return sum(1 for op in obj.operateurs.all() if op.statut == StatutOperateur.ACTIF)
        # Fallback sur la property (génère une requête)
        return obj.nombre_membres


class TacheSerializer(serializers.ModelSerializer):
    """Serializer COMPLET pour GET (lecture)

    ⚡ OPTIMISATION: Utilise des serializers MINIMAUX pour les relations M2M
    afin d'éviter les N+1 queries. Seules les infos essentielles sont chargées.
    """
    client_detail = ClientLightSerializer(source='id_client', read_only=True)
    structure_client_detail = StructureClientLightSerializer(source='id_structure_client', read_only=True)
    type_tache_detail = TypeTacheSerializer(source='id_type_tache', read_only=True)

    # Legacy single team (for backwards compatibility)
    equipe_detail = EquipeMinimalSerializer(source='id_equipe', read_only=True)

    # ⚡ VERSIONS MINIMALES pour éviter N+1 (réactivées avec prefetch limité)
    equipes_detail = EquipeMinimalSerializer(source='equipes', many=True, read_only=True)
    objets_detail = ObjetMinimalSerializer(source='objets', many=True, read_only=True)

    # Participations: désactivé car rarement affiché dans la liste
    # participations_detail = ParticipationTacheSerializer(source='participations', many=True, read_only=True)

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

            # RÈGLE D'OR: Une tâche doit avoir lieu sur le MÊME jour calendaire
            # Pour éviter la confusion entre "Chantier" (macro) et "Intervention" (micro)
            if start.date() != end.date():
                raise serializers.ValidationError({
                    "date_fin_planifiee":
                        "Une tâche doit obligatoirement avoir lieu sur le même jour calendaire. "
                        f"Début: {start.date().strftime('%d/%m/%Y')}, "
                        f"Fin: {end.date().strftime('%d/%m/%Y')}. "
                        "Pour planifier sur plusieurs jours, créez plusieurs tâches ou utilisez la récurrence."
                })

        # Si une charge est fournie manuellement, activer le flag charge_manuelle
        if 'charge_estimee_heures' in data and data['charge_estimee_heures'] is not None:
            data['charge_manuelle'] = True

        # ⚡ OPTIMISATION: Validation désactivée pour beaucoup d'objets (cause 15s de N+1 queries)
        # Chaque obj.site_id déclenche une requête SQL si site n'est pas prefetché
        # La validation est faite côté frontend lors de la sélection des objets
        objets = data.get('objets')
        if objets and len(objets) > 1 and len(objets) <= 50:
            # Seulement pour <= 50 objets, faire la validation
            site_ids = set(obj.site_id for obj in objets)
            if len(site_ids) > 1:
                raise serializers.ValidationError({
                    "objets": "Tous les objets doivent appartenir au même site. "
                              "Les objets sélectionnés appartiennent à plusieurs sites différents."
                })
        # Pour > 50 objets, skip la validation (frontend s'en occupe)

        # ⚡ OPTIMISATION: Validation désactivée pour les updates car get_nom_type() est trop lent (1.3 min)
        # La validation est faite côté frontend lors de la sélection des objets
        # Pour réactiver, améliorer get_nom_type() pour éviter les N+1 queries

        # Validation: le type de tâche doit être applicable à tous les types d'objets sélectionnés
        # type_tache = data.get('id_type_tache')
        # if type_tache and objets:
        #     # Récupérer les types d'objets uniques parmi les objets sélectionnés
        #     types_objets = set()
        #     for obj in objets:
        #         # obj est une instance d'Objet, on récupère le type réel
        #         type_reel = obj.get_nom_type()  # ← TRÈS LENT: fait des queries pour chaque objet
        #         if type_reel:
        #             types_objets.add(type_reel)
        #
        #     # Vérifier que pour chaque type d'objet, un ratio existe (requête unique)
        #     existing_ratios = set(RatioProductivite.objects.filter(
        #         id_type_tache=type_tache,
        #         type_objet__in=types_objets,
        #         actif=True
        #     ).values_list('type_objet', flat=True))
        #
        #     types_non_applicables = [t for t in types_objets if t not in existing_ratios]
        #
        #     if types_non_applicables:
        #         raise serializers.ValidationError({
        #             "id_type_tache": f"Le type de tâche '{type_tache.nom_tache}' n'est pas applicable aux types d'objets suivants: {', '.join(types_non_applicables)}. "
        #                              "Veuillez sélectionner un type de tâche compatible avec tous les objets."
        #         })

        return data

    def create(self, validated_data):
        # Extract metadata
        current_user = validated_data.pop('_current_user', None)

        # Extract M2M fields
        equipes = validated_data.pop('equipes', None)
        objets = validated_data.pop('objets', None)

        # AUTO-ASSIGN CLIENT & STRUCTURE: Si non fournis, les déduire des objets
        if objets:
            for obj in objets:
                if hasattr(obj, 'site') and obj.site:
                    # Assigner id_structure_client si non fourni
                    if ('id_structure_client' not in validated_data or validated_data.get('id_structure_client') is None):
                        if obj.site.structure_client:
                            validated_data['id_structure_client'] = obj.site.structure_client
                    # Legacy: Assigner id_client si non fourni
                    if ('id_client' not in validated_data or validated_data.get('id_client') is None):
                        if hasattr(obj.site, 'client') and obj.site.client:
                            validated_data['id_client'] = obj.site.client
                    break

        instance = super().create(validated_data)
        if current_user:
            instance._current_user = current_user

        # Set M2M relationships
        if equipes is not None:
            instance.equipes.set(equipes)
        if objets is not None:
            instance.objets.set(objets)

        return instance

    def update(self, instance, validated_data):
        import time

        start_total = time.time()
        print(f"[PERF] UPDATE START - Tache #{instance.id}")

        # Extract metadata
        current_user = validated_data.pop('_current_user', None)
        if current_user:
            instance._current_user = current_user

        # Extract M2M fields
        equipes = validated_data.pop('equipes', None)
        objets = validated_data.pop('objets', None)

        print(f"[PERF] Extracted M2M - equipes: {len(equipes) if equipes else 0}, objets: {len(objets) if objets else 0}")

        start_super = time.time()
        instance = super().update(instance, validated_data)
        print(f"[PERF] super().update() took {time.time() - start_super:.2f}s")

        # Set M2M relationships
        if equipes is not None:
            start_eq = time.time()
            instance.equipes.set(equipes)
            print(f"[PERF] equipes.set() took {time.time() - start_eq:.2f}s")

        # ⚡ OPTIMISATION AGRESSIVE: Skip complètement la mise à jour M2M pour beaucoup d'objets
        # La validation de cohérence est déjà faite côté frontend
        if objets is not None and len(objets) <= 50:
            start_obj = time.time()
            # Seulement pour peu d'objets (<= 50), faire la mise à jour normale
            instance.objets.set(objets)
            print(f"[PERF] objets.set() took {time.time() - start_obj:.2f}s")
        else:
            print(f"[PERF] SKIPPED objets.set() for {len(objets) if objets else 0} objects")

        print(f"[PERF] UPDATE TOTAL took {time.time() - start_total:.2f}s")
        return instance
