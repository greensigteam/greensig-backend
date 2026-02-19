import logging
from rest_framework import serializers
from .models import TypeTache, Tache, ParticipationTache, RatioProductivite, DistributionCharge
from api_users.models import Equipe, Client, StructureClient
from api.models import Objet

logger = logging.getLogger(__name__)


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


# ==============================================================================
# DISTRIBUTION DE CHARGE (TÂCHES MULTI-JOURS)
# ==============================================================================

class DistributionChargeSerializer(serializers.ModelSerializer):
    """
    ✅ Serializer pour les distributions de charge journalières.
    Version 2.0 avec statuts avancés et support du report chaîné.

    Permet de définir précisément la charge planifiée par jour
    pour des tâches s'étendant sur plusieurs jours.
    """
    # ✅ FIX: heures_planifiees est auto-calculé depuis heure_debut/heure_fin dans validate()
    heures_planifiees = serializers.FloatField(required=False)

    # Champs calculés pour la traçabilité des reports
    nombre_reports = serializers.SerializerMethodField(read_only=True)
    est_report = serializers.SerializerMethodField(read_only=True)
    a_remplacement = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DistributionCharge
        fields = [
            'id', 'tache', 'date',
            'heures_planifiees', 'heures_reelles',
            'heure_debut', 'heure_fin',
            # Heures réelles (saisie à froid par le superviseur)
            'heure_debut_reelle', 'heure_fin_reelle',
            'commentaire', 'status',
            # Nouveaux champs v2
            'motif_report_annulation',
            'date_demarrage', 'date_completion',
            'distribution_origine', 'distribution_remplacement',
            # Champs calculés
            'nombre_reports', 'est_report', 'a_remplacement',
            'reference',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reference',
            'date_demarrage', 'date_completion',  # Horodatés automatiquement
            'distribution_origine', 'distribution_remplacement',  # Gérés par les actions
            'nombre_reports', 'est_report', 'a_remplacement',
            'created_at', 'updated_at'
        ]

    def get_nombre_reports(self, obj) -> int:
        """
        Retourne le nombre de reports dans la chaîne.

        ⚡ OPTIMISATION: Évite le calcul coûteux si pas nécessaire.
        """
        if not obj.pk:
            return 0
        # Si cette distribution n'a jamais été impliquée dans un report, retourner 0
        if obj.distribution_origine_id is None and obj.distribution_remplacement_id is None:
            return 0
        return obj.get_nombre_reports()

    def get_est_report(self, obj) -> bool:
        """Retourne True si cette distribution est issue d'un report."""
        return obj.distribution_origine_id is not None if obj.pk else False

    def get_a_remplacement(self, obj) -> bool:
        """Retourne True si cette distribution a été reportée (a un remplacement)."""
        return obj.distribution_remplacement_id is not None if obj.pk else False

    def get_fields(self):
        """Rendre 'tache' read-only uniquement lors de l'update"""
        fields = super().get_fields()
        # Si c'est un update (instance existe), rendre 'tache' read-only
        if self.instance is not None:
            fields['tache'].read_only = True
        return fields

    def validate(self, data):
        """Validation de la distribution"""
        # Récupérer la tâche (depuis data pour création, depuis instance pour update)
        tache = data.get('tache')
        if not tache and self.instance:
            tache = self.instance.tache

        # Récupérer la date (depuis data ou depuis instance pour update partiel)
        date = data.get('date')
        if not date and self.instance:
            date = self.instance.date

        # Vérifier que la date est dans la période de la tâche
        if tache and date:
            # Les dates sont déjà des DateField (datetime.date)
            date_debut = tache.date_debut_planifiee
            date_fin = tache.date_fin_planifiee

            if date < date_debut or date > date_fin:
                raise serializers.ValidationError({
                    'date': f"La date doit être comprise entre {date_debut} et {date_fin}"
                })

            # Vérifier l'unicité (tache, date) sauf pour l'instance en cours de modification
            from api_planification.models import DistributionCharge
            existing_query = DistributionCharge.objects.filter(tache=tache, date=date)

            # Si c'est un update, exclure l'instance actuelle
            if self.instance:
                existing_query = existing_query.exclude(id=self.instance.id)

            if existing_query.exists():
                raise serializers.ValidationError({
                    'date': f"Une distribution existe déjà pour cette tâche à la date du {date.strftime('%d/%m/%Y')}"
                })

        # Récupérer heure_debut et heure_fin (depuis data ou depuis instance pour update partiel)
        heure_debut = data.get('heure_debut')
        if not heure_debut and self.instance:
            heure_debut = self.instance.heure_debut

        heure_fin = data.get('heure_fin')
        if not heure_fin and self.instance:
            heure_fin = self.instance.heure_fin

        # Vérifier que heure_fin > heure_debut
        if heure_debut and heure_fin:
            if heure_fin <= heure_debut:
                raise serializers.ValidationError({
                    'heure_fin': "L'heure de fin doit être postérieure à l'heure de début"
                })

            # Calcul automatique des heures_planifiees si heure_debut et heure_fin sont définies
            from datetime import datetime, timedelta
            debut = datetime.combine(datetime.today(), heure_debut)
            fin = datetime.combine(datetime.today(), heure_fin)
            diff = fin - debut
            heures = diff.total_seconds() / 3600
            data['heures_planifiees'] = round(heures, 2) if heures > 0 else 0

        return data


class DistributionChargeEnrichedSerializer(serializers.ModelSerializer):
    """
    Serializer enrichi pour les distributions avec les informations de la tâche associée.
    Utilisé pour la vue "Distributions par jour" dans le suivi des tâches.
    """
    # Informations de la distribution
    nombre_reports = serializers.SerializerMethodField(read_only=True)
    est_report = serializers.SerializerMethodField(read_only=True)
    a_remplacement = serializers.SerializerMethodField(read_only=True)

    # Informations de la tâche (enrichissement)
    tache_id = serializers.IntegerField(source='tache.id', read_only=True)
    tache_titre = serializers.SerializerMethodField(read_only=True)
    tache_type = serializers.SerializerMethodField(read_only=True)
    tache_statut = serializers.CharField(source='tache.statut', read_only=True)
    tache_site_nom = serializers.SerializerMethodField(read_only=True)
    tache_equipes = serializers.SerializerMethodField(read_only=True)
    tache_priorite = serializers.CharField(source='tache.priorite', read_only=True)
    tache_reference = serializers.CharField(source='tache.reference', read_only=True, allow_null=True)

    class Meta:
        model = DistributionCharge
        fields = [
            'id', 'tache', 'date',
            'heures_planifiees', 'heures_reelles',
            'heure_debut', 'heure_fin',
            # Heures réelles (saisie à froid par le superviseur)
            'heure_debut_reelle', 'heure_fin_reelle',
            'commentaire', 'status',
            'motif_report_annulation',
            'date_demarrage', 'date_completion',
            'distribution_origine', 'distribution_remplacement',
            'nombre_reports', 'est_report', 'a_remplacement',
            'reference',
            'created_at', 'updated_at',
            # Champs enrichis de la tâche
            'tache_id', 'tache_titre', 'tache_type', 'tache_statut',
            'tache_site_nom', 'tache_equipes', 'tache_priorite', 'tache_reference'
        ]
        read_only_fields = fields  # Tout est read-only pour ce serializer de lecture

    def get_nombre_reports(self, obj) -> int:
        """
        Retourne le nombre de reports dans la chaîne.

        ⚡ OPTIMISATION: Évite le calcul coûteux si pas nécessaire.
        """
        if not obj.pk:
            return 0
        # Si cette distribution n'a jamais été impliquée dans un report, retourner 0
        if obj.distribution_origine_id is None and obj.distribution_remplacement_id is None:
            return 0
        return obj.get_nombre_reports()

    def get_est_report(self, obj) -> bool:
        """Retourne True si cette distribution est issue d'un report."""
        return obj.distribution_origine_id is not None if obj.pk else False

    def get_a_remplacement(self, obj) -> bool:
        """Retourne True si cette distribution a été reportée (a un remplacement)."""
        return obj.distribution_remplacement_id is not None if obj.pk else False

    def get_tache_titre(self, obj) -> str:
        """Retourne le titre de la tâche (type + reference)."""
        tache = obj.tache
        if tache:
            type_nom = tache.id_type_tache.nom_tache if tache.id_type_tache else "Tâche"
            ref = tache.reference or f"#{tache.id}"
            return f"{type_nom} - {ref}"
        return None

    def get_tache_type(self, obj) -> str:
        """Retourne le nom du type de tâche."""
        tache = obj.tache
        if tache and tache.id_type_tache:
            return tache.id_type_tache.nom_tache
        return None

    def get_tache_site_nom(self, obj) -> str:
        """Retourne le nom du premier site de la tâche (via les objets)."""
        tache = obj.tache
        if tache:
            try:
                # Utiliser les données prefetchées si disponibles
                objets = getattr(tache, '_prefetched_objects_cache', {}).get('objets')
                if objets is None:
                    objets = list(tache.objets.all()[:1])
                else:
                    objets = list(objets)[:1]

                if objets and objets[0].site:
                    return objets[0].site.nom_site
            except Exception:
                pass
        return None

    def get_tache_equipes(self, obj) -> list:
        """Retourne la liste des noms d'équipes assignées à la tâche."""
        tache = obj.tache
        if tache and hasattr(tache, 'equipes'):
            try:
                # Utiliser prefetch_related pour éviter N+1
                equipes = getattr(tache, '_prefetched_objects_cache', {}).get('equipes')
                if equipes is None:
                    equipes = tache.equipes.all()
                return [e.nom_equipe for e in equipes]
            except Exception:
                return []
        return []


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

    # ✅ Site déduit (depuis objets OU réclamation)
    site_id = serializers.SerializerMethodField()
    site_nom = serializers.SerializerMethodField()

    def get_site_id(self, obj):
        """
        Retourne le site_id déduit des objets ou de la réclamation.

        ⚡ OPTIMISATION: Utilise les données prefetchées pour éviter N+1.
        """
        # 1. D'abord essayer depuis les objets prefetchés
        objets_cache = getattr(obj, '_prefetched_objects_cache', {}).get('objets')
        if objets_cache is not None:
            # Utiliser les données prefetchées
            for objet in objets_cache:
                if objet.site_id:
                    return objet.site_id
        elif obj.objets.exists():
            # Fallback si pas prefetché (devrait être rare)
            first_obj = obj.objets.first()
            if first_obj and first_obj.site_id:
                return first_obj.site_id

        # 2. Sinon depuis la réclamation (déjà select_related dans le viewset)
        if obj.reclamation and obj.reclamation.site_id:
            return obj.reclamation.site_id
        return None

    def get_site_nom(self, obj):
        """
        Retourne le nom du site déduit des objets ou de la réclamation.

        ⚡ OPTIMISATION: Utilise les données prefetchées pour éviter N+1.
        Le viewset prefetch 'objets__site' donc site.nom_site est déjà chargé.
        """
        # 1. D'abord essayer depuis les objets prefetchés
        objets_cache = getattr(obj, '_prefetched_objects_cache', {}).get('objets')
        if objets_cache is not None:
            # Utiliser les données prefetchées
            for objet in objets_cache:
                if objet.site:
                    return objet.site.nom_site
        elif obj.objets.exists():
            # Fallback si pas prefetché (devrait être rare)
            first_obj = obj.objets.select_related('site').first()
            if first_obj and first_obj.site:
                return first_obj.site.nom_site

        # 2. Sinon depuis la réclamation (déjà select_related dans le viewset)
        if obj.reclamation and obj.reclamation.site:
            return obj.reclamation.site.nom_site
        return None

    # ✅ NOUVEAU: Distributions de charge pour tâches multi-jours
    distributions_charge = DistributionChargeSerializer(many=True, read_only=True)
    charge_totale_distributions = serializers.FloatField(read_only=True)
    nombre_jours_travail = serializers.IntegerField(read_only=True)

    # ✅ NOUVEAU: Temps de travail total (Option 2: Approche Hybride)
    temps_travail_total = serializers.SerializerMethodField()

    def get_temps_travail_total(self, obj):
        """
        Retourne le temps de travail total calculé avec toutes les métadonnées.

        Returns:
            dict: {
                'heures': float,
                'source': str,
                'fiable': bool,
                'manuel': bool,
                'manuel_par': str|None,
                'manuel_date': str|None
            }
        """
        return obj.temps_travail_total

    # ✅ DYNAMIQUE: Statut calculé en temps réel (remplace le statut stocké)
    statut = serializers.SerializerMethodField()
    statut_stocke = serializers.CharField(source='statut', read_only=True)

    def get_statut(self, obj):
        """Retourne le statut calculé dynamiquement au lieu du statut stocké."""
        return obj.computed_statut

    class Meta:
        model = Tache
        fields = '__all__'


class TacheListSerializer(serializers.ModelSerializer):
    """
    ⚡ Serializer OPTIMISÉ pour la LISTE des tâches (GET /taches/).

    Évite les requêtes N+1 en utilisant:
    - Le statut stocké au lieu de computed_statut
    - Les données préchargées via prefetch_related
    - Les annotations du queryset pour les agrégations

    Le serializer complet (TacheSerializer) reste utilisé pour:
    - GET /taches/{id}/ (détail)
    - Les réponses après création/modification
    """
    # Relations préchargées (serializers minimaux)
    client_detail = ClientLightSerializer(source='id_client', read_only=True)
    structure_client_detail = StructureClientLightSerializer(source='id_structure_client', read_only=True)
    type_tache_detail = TypeTacheSerializer(source='id_type_tache', read_only=True)
    equipe_detail = EquipeMinimalSerializer(source='id_equipe', read_only=True)
    equipes_detail = EquipeMinimalSerializer(source='equipes', many=True, read_only=True)
    objets_detail = ObjetMinimalSerializer(source='objets', many=True, read_only=True)

    reclamation_numero = serializers.CharField(source='reclamation.numero_reclamation', read_only=True, allow_null=True)

    # ⚡ Site déduit depuis les données PRÉCHARGÉES (pas de requête supplémentaire)
    site_id = serializers.SerializerMethodField()
    site_nom = serializers.SerializerMethodField()

    def get_site_id(self, obj):
        """Utilise les objets préchargés pour éviter les requêtes N+1."""
        # Utiliser le cache prefetch si disponible
        objets_cache = getattr(obj, '_prefetched_objects_cache', {})
        if 'objets' in objets_cache:
            objets = objets_cache['objets']
            if objets:
                first_obj = objets[0]
                if first_obj.site_id:
                    return first_obj.site_id
        # Fallback sur la réclamation (déjà select_related)
        if obj.reclamation and obj.reclamation.site_id:
            return obj.reclamation.site_id
        return None

    def get_site_nom(self, obj):
        """Utilise les objets préchargés pour éviter les requêtes N+1."""
        objets_cache = getattr(obj, '_prefetched_objects_cache', {})
        if 'objets' in objets_cache:
            objets = objets_cache['objets']
            if objets:
                first_obj = objets[0]
                # site est préchargé via prefetch_related('objets__site')
                if first_obj.site:
                    return first_obj.site.nom_site
        # Fallback sur la réclamation
        if obj.reclamation and obj.reclamation.site:
            return obj.reclamation.site.nom_site
        return None

    # ⚡ Distributions préchargées
    distributions_charge = DistributionChargeSerializer(many=True, read_only=True)

    # ⚡ Agrégations via ANNOTATIONS (calculées dans le queryset, pas par tâche)
    # Les annotations sont nommées _annot_* pour éviter conflit avec les propriétés du modèle
    charge_totale_distributions = serializers.SerializerMethodField()
    nombre_jours_travail = serializers.SerializerMethodField()

    def get_charge_totale_distributions(self, obj):
        """Utilise l'annotation si disponible, sinon 0."""
        return getattr(obj, '_annot_charge_totale', None) or 0.0

    def get_nombre_jours_travail(self, obj):
        """Utilise l'annotation si disponible, sinon 0."""
        return getattr(obj, '_annot_nombre_jours', None) or 0

    class Meta:
        model = Tache
        fields = [
            'id', 'reference', 'id_structure_client', 'id_client', 'id_type_tache',
            'id_equipe', 'equipes', 'date_debut_planifiee', 'date_fin_planifiee',
            'date_echeance', 'priorite', 'commentaires', 'date_affectation',
            'date_debut_reelle', 'date_fin_reelle', 'duree_reelle_minutes',
            'charge_estimee_heures', 'charge_manuelle', 'description_travaux',
            'statut', 'note_qualite', 'etat_validation', 'date_validation',
            'validee_par', 'commentaire_validation', 'notifiee', 'confirmee',
            'reclamation', 'date_creation', 'objets',
            # Champs calculés/relations
            'client_detail', 'structure_client_detail', 'type_tache_detail',
            'equipe_detail', 'equipes_detail', 'objets_detail',
            'reclamation_numero', 'site_id', 'site_nom',
            'distributions_charge', 'charge_totale_distributions', 'nombre_jours_travail',
        ]


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

    # ✅ NOUVEAU: Distributions de charge (write-only pour création/update)
    distributions_charge_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="Liste des distributions: [{'date': '2024-01-15', 'heures_planifiees': 2.0}, ...]"
    )

    # ✅ NOUVEAU: Configuration de récurrence (ignorée par le backend, gérée par le frontend)
    recurrence_config = serializers.DictField(
        write_only=True,
        required=False,
        help_text="Configuration de récurrence (géré côté frontend après création)"
    )

    class Meta:
        model = Tache
        fields = '__all__'
        read_only_fields = []

    def validate(self, data):
        start = data.get('date_debut_planifiee')
        end = data.get('date_fin_planifiee')

        # ✅ CHANGEMENT: Contrainte "même jour" retirée pour permettre tâches multi-jours
        # La distribution de charge par jour est gérée via le modèle DistributionCharge
        if start and end:
            if end < start:
                raise serializers.ValidationError({"date_fin_planifiee": "La date de fin ne peut pas être antérieure à la date de début."})

        # ══════════════════════════════════════════════════════════════════════════
        # VALIDATIONS MÉTIER - TRANSITIONS DE STATUT
        # ══════════════════════════════════════════════════════════════════════════
        nouveau_statut = data.get('statut')

        if nouveau_statut and self.instance:
            ancien_statut = self.instance.statut

            # Matrice des transitions valides
            # Format: {statut_actuel: [statuts_autorisés]}
            TRANSITIONS_VALIDES = {
                'PLANIFIEE': ['EN_COURS', 'ANNULEE'],
                'EN_COURS': ['TERMINEE', 'ANNULEE'],
                'ANNULEE': ['PLANIFIEE'],  # Réactivation via replanification
                'TERMINEE': ['VALIDEE', 'REJETEE'],  # Validation uniquement
                'REJETEE': ['PLANIFIEE'],  # Replanification après rejet
                'VALIDEE': [],  # Aucune transition (statut final)
            }

            transitions_autorisees = TRANSITIONS_VALIDES.get(ancien_statut, [])

            if nouveau_statut != ancien_statut and nouveau_statut not in transitions_autorisees:
                raise serializers.ValidationError({
                    "statut": f"Transition de statut invalide: {ancien_statut} → {nouveau_statut}. "
                              f"Transitions autorisées depuis '{ancien_statut}': {', '.join(transitions_autorisees) if transitions_autorisees else 'aucune'}."
                })

        # ══════════════════════════════════════════════════════════════════════════
        # VALIDATION DÉMARRAGE (EN_COURS)
        # ══════════════════════════════════════════════════════════════════════════
        if nouveau_statut == 'EN_COURS':
            from django.utils import timezone
            today = timezone.now().date()

            # 1. Impossible de démarrer avant la date de début planifiée
            date_debut = start
            if not date_debut and self.instance:
                date_debut = self.instance.date_debut_planifiee

            if date_debut and date_debut > today:
                raise serializers.ValidationError({
                    "statut": f"Impossible de démarrer la tâche avant sa date de début planifiée ({date_debut.strftime('%d/%m/%Y')}). "
                              f"Veuillez attendre le {date_debut.strftime('%d/%m/%Y')} ou modifier la date de début."
                })

            # 2. Impossible de démarrer sans équipe assignée
            equipes = data.get('equipes')
            if equipes is None and self.instance:
                # Vérifier les équipes existantes (M2M ou legacy)
                has_equipe = self.instance.equipes.exists() or self.instance.equipe is not None
            else:
                has_equipe = equipes and len(equipes) > 0

            if not has_equipe:
                raise serializers.ValidationError({
                    "statut": "Impossible de démarrer la tâche sans équipe assignée. "
                              "Veuillez assigner au moins une équipe avant de démarrer."
                })

        # ══════════════════════════════════════════════════════════════════════════
        # VALIDATION TERMINER (TERMINEE)
        # ══════════════════════════════════════════════════════════════════════════
        if nouveau_statut == 'TERMINEE' and self.instance:
            # 1. Impossible de terminer sans équipe assignée
            equipes = data.get('equipes')
            if equipes is None:
                has_equipe = self.instance.equipes.exists() or self.instance.equipe is not None
            else:
                has_equipe = equipes and len(equipes) > 0

            if not has_equipe:
                raise serializers.ValidationError({
                    "statut": "Impossible de terminer la tâche sans équipe assignée. "
                              "Veuillez assigner au moins une équipe."
                })

            # 2. Impossible de terminer si des distributions sont encore actives
            from .business_rules import valider_terminaison_tache
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                valider_terminaison_tache(self.instance)
            except DjangoValidationError as e:
                raise serializers.ValidationError({
                    "statut": str(e.message)
                })

        # ══════════════════════════════════════════════════════════════════════════
        # VALIDATION ANNULER (ANNULEE)
        # ══════════════════════════════════════════════════════════════════════════
        if nouveau_statut == 'ANNULEE' and self.instance:
            # Impossible d'annuler une tâche terminée ou validée
            if self.instance.statut in ('TERMINEE', 'VALIDEE', 'REJETEE'):
                raise serializers.ValidationError({
                    "statut": f"Impossible d'annuler une tâche {self.instance.statut.lower()}. "
                              "Les tâches terminées ou validées ne peuvent pas être annulées."
                })

            # Motif d'annulation OBLIGATOIRE
            motif_annulation = data.get('motif_annulation')
            if not motif_annulation:
                raise serializers.ValidationError({
                    "motif_annulation": "Le motif d'annulation est obligatoire pour annuler une tâche."
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

        # ✅ NOUVEAU: Extract distributions de charge
        distributions_data = validated_data.pop('distributions_charge_data', None)

        # ✅ NOUVEAU: Extract recurrence config (ignoré, géré côté frontend)
        recurrence_config = validated_data.pop('recurrence_config', None)

        # AUTO-ASSIGN CLIENT & STRUCTURE: Si non fournis, les déduire des objets OU de la réclamation
        site_found = None

        # 1. D'abord essayer de déduire depuis les objets
        if objets:
            for obj in objets:
                if hasattr(obj, 'site') and obj.site:
                    site_found = obj.site
                    break

        # 2. Sinon, essayer de déduire depuis la réclamation liée
        if not site_found and validated_data.get('reclamation'):
            reclamation = validated_data.get('reclamation')
            if hasattr(reclamation, 'site') and reclamation.site:
                site_found = reclamation.site

        # 3. Assigner id_structure_client et id_client depuis le site trouvé
        if site_found:
            if ('id_structure_client' not in validated_data or validated_data.get('id_structure_client') is None):
                if site_found.structure_client:
                    validated_data['id_structure_client'] = site_found.structure_client
            if ('id_client' not in validated_data or validated_data.get('id_client') is None):
                if hasattr(site_found, 'client') and site_found.client:
                    validated_data['id_client'] = site_found.client

        instance = super().create(validated_data)
        if current_user:
            instance._current_user = current_user

        # Set M2M relationships
        if equipes is not None:
            instance.equipes.set(equipes)
        if objets is not None:
            instance.objets.set(objets)

        # ✅ NOUVEAU: Créer les distributions de charge
        from datetime import datetime

        # ✅ Créer les distributions de charge uniquement si fournies explicitement par le frontend
        if distributions_data:
            for dist_data in distributions_data:
                # Récupérer les heures (assurer qu'elles ne sont pas None)
                heure_debut_str = dist_data.get('heure_debut') or '08:00'
                heure_fin_str = dist_data.get('heure_fin') or '17:00'

                # Nettoyer et parser les heures (format HH:MM ou HH:MM:SS)
                try:
                    # Prendre seulement les 5 premiers caractères (HH:MM)
                    if isinstance(heure_debut_str, str):
                        heure_debut_clean = heure_debut_str.split('.')[0][:5]
                    else:
                        heure_debut_clean = '08:00'

                    if isinstance(heure_fin_str, str):
                        heure_fin_clean = heure_fin_str.split('.')[0][:5]
                    else:
                        heure_fin_clean = '17:00'

                    heure_debut = datetime.strptime(heure_debut_clean, '%H:%M').time()
                    heure_fin = datetime.strptime(heure_fin_clean, '%H:%M').time()
                except (ValueError, AttributeError) as e:
                    # Fallback sur des valeurs par défaut
                    heure_debut = datetime.strptime('08:00', '%H:%M').time()
                    heure_fin = datetime.strptime('17:00', '%H:%M').time()

                # Calculer les heures
                debut = datetime.combine(datetime.today(), heure_debut)
                fin = datetime.combine(datetime.today(), heure_fin)
                diff = fin - debut
                heures_planifiees = round(diff.total_seconds() / 3600, 2) if diff.total_seconds() > 0 else 0

                DistributionCharge.objects.create(
                    tache=instance,
                    date=dist_data['date'],
                    heures_planifiees=heures_planifiees,
                    heure_debut=heure_debut,
                    heure_fin=heure_fin,
                    commentaire=dist_data.get('commentaire', '')
                )
        # Gérer la récurrence automatique si configurée
        if recurrence_config and recurrence_config.get('enabled'):
            mode = recurrence_config.get('mode')

            if mode == 'frequency':
                # Import des fonctions de duplication
                from .utils import (
                    dupliquer_tache_recurrence_multiple,
                    dupliquer_tache_recurrence_jours_semaine,
                    dupliquer_tache_recurrence_jours_mois
                )
                from django.core.exceptions import ValidationError as DjangoValidationError

                frequency = recurrence_config.get('frequency')
                jours_semaine = recurrence_config.get('jours_semaine')
                jours_mois = recurrence_config.get('jours_mois')
                nombre_occurrences = recurrence_config.get('nombre_occurrences')
                date_fin_recurrence = recurrence_config.get('date_fin_recurrence')
                conserver_equipes = recurrence_config.get('conserver_equipes', True)
                conserver_objets = recurrence_config.get('conserver_objets', True)

                # Convertir date_fin_recurrence si c'est une chaîne
                if date_fin_recurrence and isinstance(date_fin_recurrence, str):
                    from datetime import datetime as dt
                    try:
                        date_fin_recurrence = dt.strptime(date_fin_recurrence, '%Y-%m-%d').date()
                    except ValueError:
                        date_fin_recurrence = None

                try:
                    nouvelles_taches = []

                    if jours_semaine and frequency == 'WEEKLY':
                        nouvelles_taches = dupliquer_tache_recurrence_jours_semaine(
                            tache_id=instance.id,
                            jours_semaine=jours_semaine,
                            nombre_occurrences=nombre_occurrences,
                            date_fin_recurrence=date_fin_recurrence,
                            conserver_equipes=conserver_equipes,
                            conserver_objets=conserver_objets,
                            nouveau_statut='PLANIFIEE'
                        )
                    elif jours_mois and frequency == 'MONTHLY':
                        nouvelles_taches = dupliquer_tache_recurrence_jours_mois(
                            tache_id=instance.id,
                            jours_mois=jours_mois,
                            nombre_occurrences=nombre_occurrences,
                            date_fin_recurrence=date_fin_recurrence,
                            conserver_equipes=conserver_equipes,
                            conserver_objets=conserver_objets,
                            nouveau_statut='PLANIFIEE'
                        )
                    else:
                        nouvelles_taches = dupliquer_tache_recurrence_multiple(
                            tache_id=instance.id,
                            frequence=frequency,
                            nombre_occurrences=nombre_occurrences,
                            date_fin_recurrence=date_fin_recurrence,
                            conserver_equipes=conserver_equipes,
                            conserver_objets=conserver_objets,
                            nouveau_statut='PLANIFIEE'
                        )

                except DjangoValidationError as e:
                    raise serializers.ValidationError({
                        'recurrence_config': f"Impossible de créer les occurrences: {str(e)}"
                    })
                except Exception as e:
                    logger.error(f"Erreur récurrence tâche #{instance.id}: {e}")
                    raise serializers.ValidationError({
                        'recurrence_config': f"Erreur lors de la création des occurrences: {str(e)}"
                    })

        return instance

    def update(self, instance, validated_data):
        # Capturer le statut explicite AVANT tout pop
        statut_explicite_initial = validated_data.get('statut')

        # Extract metadata
        current_user = validated_data.pop('_current_user', None)
        if current_user:
            instance._current_user = current_user

        # Extract M2M fields
        equipes = validated_data.pop('equipes', None)
        objets = validated_data.pop('objets', None)

        # ✅ NOUVEAU: Extract distributions de charge
        distributions_data = validated_data.pop('distributions_charge_data', None)

        # ✅ NOUVEAU: Extract recurrence config (ignoré en update, seulement pour create)
        recurrence_config = validated_data.pop('recurrence_config', None)

        # Capturer l'ancien statut avant la mise à jour
        ancien_statut_stocke = instance.statut
        # ✅ FIX: Utiliser le statut calculé pour refléter l'état réel (ce que l'utilisateur voit)
        ancien_statut_calcule = instance.computed_statut

        instance = super().update(instance, validated_data)

        # ✅ ANNULATION: Remplir automatiquement date_annulation et annulee_par
        if statut_explicite_initial == 'ANNULEE' and ancien_statut_stocke != 'ANNULEE':
            from django.utils import timezone
            instance.date_annulation = timezone.now()
            if current_user:
                instance.annulee_par = current_user
            instance.save(update_fields=['date_annulation', 'annulee_par'])

        # ✅ REPLANIFICATION: Nettoyer les champs d'annulation quand on réactive une tâche
        if ancien_statut_stocke == 'ANNULEE' and statut_explicite_initial and statut_explicite_initial != 'ANNULEE':
            instance.motif_annulation = None
            instance.commentaire_annulation = ''
            instance.date_annulation = None
            instance.annulee_par = None
            instance.save(update_fields=['motif_annulation', 'commentaire_annulation', 'date_annulation', 'annulee_par'])

        # Set M2M relationships
        if equipes is not None:
            instance.equipes.set(equipes)

        # ⚡ OPTIMISATION AGRESSIVE: Skip complètement la mise à jour M2M pour beaucoup d'objets
        # La validation de cohérence est déjà faite côté frontend
        if objets is not None and len(objets) <= 50:
            instance.objets.set(objets)

        # ✅ NOUVEAU: Mettre à jour les distributions de charge (Smart Update)
        if distributions_data is not None:
            from datetime import datetime
            from .business_rules import valider_suppression_distributions_bulk

            # 1. Identifier les IDs à conserver (ceux présents dans la payload)
            ids_to_keep = [item.get('id') for item in distributions_data if item.get('id')]

            # 2. Identifier les distributions à supprimer
            distributions_a_supprimer = instance.distributions_charge.exclude(id__in=ids_to_keep)

            # 3. Valider la suppression via les règles métier centralisées
            if distributions_a_supprimer.exists():
                valider_suppression_distributions_bulk(
                    tache=instance,
                    distributions_a_supprimer=distributions_a_supprimer,
                    distributions_a_conserver=len(distributions_data)
                )
                # Supprimer les distributions (validations passées)
                distributions_a_supprimer.delete()

            # 3. Créer ou Mettre à jour
            for dist_data in distributions_data:
                # Récupérer les heures (assurer qu'elles ne sont pas None)
                heure_debut_str = dist_data.get('heure_debut') or '08:00'
                heure_fin_str = dist_data.get('heure_fin') or '17:00'

                # Nettoyer et parser les heures (format HH:MM ou HH:MM:SS)
                try:
                    # Prendre seulement les 5 premiers caractères (HH:MM)
                    if isinstance(heure_debut_str, str):
                        heure_debut_clean = heure_debut_str.split('.')[0][:5]
                    else:
                        heure_debut_clean = '08:00'

                    if isinstance(heure_fin_str, str):
                        heure_fin_clean = heure_fin_str.split('.')[0][:5]
                    else:
                        heure_fin_clean = '17:00'

                    heure_debut = datetime.strptime(heure_debut_clean, '%H:%M').time()
                    heure_fin = datetime.strptime(heure_fin_clean, '%H:%M').time()
                except (ValueError, AttributeError) as e:
                    # Fallback sur des valeurs par défaut
                    heure_debut = datetime.strptime('08:00', '%H:%M').time()
                    heure_fin = datetime.strptime('17:00', '%H:%M').time()

                # Calculer les heures
                debut = datetime.combine(datetime.today(), heure_debut)
                fin = datetime.combine(datetime.today(), heure_fin)
                diff = fin - debut
                heures_planifiees = round(diff.total_seconds() / 3600, 2) if diff.total_seconds() > 0 else 0

                # ✅ FIX: Extraire l'ID de la distribution (si elle existe déjà)
                dist_id = dist_data.get('id')

                if dist_id:
                    # --- UPDATE ---
                    try:
                        dist = instance.distributions_charge.get(id=dist_id)
                        
                        # ✅ PROTECTION: Si REALISEE, on interdit la modification des données planifiées
                        if dist.status == 'REALISEE':
                            # Autoriser seulement l'update du commentaire pour les distributions réalisées
                            if 'commentaire' in dist_data and dist_data['commentaire'] != dist.commentaire:
                                dist.commentaire = dist_data['commentaire']
                                dist.save(update_fields=['commentaire'])
                        else:
                            # Mise à jour complète pour les distributions non réalisées
                            dist.date = dist_data['date']
                            dist.heures_planifiees = heures_planifiees
                            dist.heure_debut = heure_debut
                            dist.heure_fin = heure_fin
                            dist.commentaire = dist_data.get('commentaire', '')
                            if 'status' in dist_data:
                                dist.status = dist_data['status']
                            # ❌ NE JAMAIS modifier 'reference' - elle est immuable une fois créée
                            # if 'reference' in dist_data:
                            #     dist.reference = dist_data['reference']
                            dist.save()
                    except DistributionCharge.DoesNotExist:
                        # Si l'ID fourni n'existe pas (ou n'appartient pas à cette tâche), on crée
                        # ❌ NE PAS passer 'reference' - elle sera auto-générée par le modèle
                        DistributionCharge.objects.create(
                            tache=instance,
                            date=dist_data['date'],
                            heures_planifiees=heures_planifiees,
                            heure_debut=heure_debut,
                            heure_fin=heure_fin,
                            commentaire=dist_data.get('commentaire', ''),
                            status=dist_data.get('status', 'NON_REALISEE')
                            # reference sera auto-générée
                        )
                else:
                    # --- CREATE ---
                    # ❌ NE PAS passer 'reference' - elle sera auto-générée par le modèle
                    new_dist = DistributionCharge.objects.create(
                        tache=instance,
                        date=dist_data['date'],
                        heures_planifiees=heures_planifiees,
                        heure_debut=heure_debut,
                        heure_fin=heure_fin,
                        commentaire=dist_data.get('commentaire', ''),
                        status=dist_data.get('status', 'NON_REALISEE')
                        # reference sera auto-générée
                    )

        # REPLANIFICATION: Restaurer les distributions APRÈS le traitement de distributions_data
        # Le frontend envoie les distributions avec leur ancien status='ANNULEE',
        # ce qui écrasait la restauration si elle était faite avant.
        if ancien_statut_calcule == 'ANNULEE':
            from .business_rules import restaurer_distributions_apres_replanification
            nb_restaurees = restaurer_distributions_apres_replanification(instance)

        # Synchroniser le statut stocké avec le statut calculé dynamiquement
        # Ne PAS synchroniser si le statut a été explicitement défini dans la requête

        if statut_explicite_initial is None:
            # Pas de statut explicite → synchronisation automatique autorisée
            instance.refresh_from_db()  # Recharger pour avoir les distributions à jour
            computed = instance.computed_statut
            if instance.statut != computed:
                instance.statut = computed
                instance.save(update_fields=['statut'])

        return instance


# =============================================================================
# SERIALIZERS POUR LA RÉCURRENCE DES TÂCHES
# =============================================================================

class DupliquerTacheSerializer(serializers.Serializer):
    """
    Serializer pour dupliquer une tâche avec décalage personnalisé.
    """
    decalage_jours = serializers.IntegerField(
        min_value=1,
        help_text="Décalage en jours entre chaque occurrence"
    )
    nombre_occurrences = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        allow_null=True,
        help_text="Nombre max de tâches à créer (optionnel, max 100)"
    )
    date_fin_recurrence = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Date limite pour créer des occurrences (optionnel). Si non fournie, génère jusqu'au 31/12 de l'année en cours"
    )
    conserver_equipes = serializers.BooleanField(
        default=True,
        help_text="Conserver les équipes assignées"
    )
    conserver_objets = serializers.BooleanField(
        default=True,
        help_text="Conserver les objets liés (sites/inventaire)"
    )
    nouveau_statut = serializers.ChoiceField(
        choices=Tache.STATUT_CHOICES,
        default='PLANIFIEE',
        help_text="Statut des nouvelles tâches créées"
    )

    def validate(self, data):
        """Validation globale."""
        nombre_occurrences = data.get('nombre_occurrences')
        date_fin_recurrence = data.get('date_fin_recurrence')

        # Au moins un des deux doit être fourni (ou aucun pour défaut)
        # Cette logique est OK

        return data


class DupliquerTacheRecurrenceSerializer(serializers.Serializer):
    """
    Serializer pour dupliquer une tâche selon une fréquence prédéfinie.
    Version 2.0 : Support de la sélection de jours de la semaine pour DAILY et WEEKLY.
    """
    FREQUENCE_CHOICES = [
        ('DAILY', 'Quotidien'),
        ('WEEKLY', 'Hebdomadaire'),
        ('MONTHLY', 'Mensuel'),
        ('YEARLY', 'Annuel'),
    ]

    frequence = serializers.ChoiceField(
        choices=FREQUENCE_CHOICES,
        help_text="Fréquence de récurrence"
    )

    # ✅ Sélection des jours de la semaine (WEEKLY uniquement)
    jours_semaine = serializers.ListField(
        child=serializers.IntegerField(min_value=0, max_value=6),
        required=False,
        allow_null=True,
        allow_empty=False,
        help_text="Liste des jours de la semaine (0=Lundi, 6=Dimanche). "
                  "Compatible avec WEEKLY uniquement. "
                  "Si non fourni, utilise le décalage standard."
    )

    # ✅ NOUVEAU: Sélection des jours du mois (MONTHLY)
    jours_mois = serializers.ListField(
        child=serializers.IntegerField(min_value=1, max_value=31),
        required=False,
        allow_null=True,
        allow_empty=False,
        help_text="Liste des jours du mois (1-31). "
                  "Compatible avec MONTHLY uniquement. "
                  "Si non fourni, utilise le décalage standard."
    )

    nombre_occurrences = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        allow_null=True,
        help_text="Nombre max d'occurrences (optionnel, max 100)"
    )
    date_fin_recurrence = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Date limite pour créer des occurrences (optionnel). Si non fournie, génère jusqu'au 31/12 de l'année en cours"
    )
    conserver_equipes = serializers.BooleanField(
        default=True,
        help_text="Conserver les équipes assignées"
    )
    conserver_objets = serializers.BooleanField(
        default=True,
        help_text="Conserver les objets liés (sites/inventaire)"
    )
    nouveau_statut = serializers.ChoiceField(
        choices=Tache.STATUT_CHOICES,
        default='PLANIFIEE',
        help_text="Statut des nouvelles tâches créées"
    )

    def validate_jours_semaine(self, value):
        """
        Validation de la liste des jours de la semaine:
        - Pas de doublons
        - Tri automatique
        - Au moins 1 jour si fourni
        """
        if value is None:
            return value

        if len(value) == 0:
            raise serializers.ValidationError(
                "Si vous spécifiez 'jours_semaine', vous devez sélectionner au moins 1 jour"
            )

        # Vérifier les doublons
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "La liste des jours contient des doublons"
            )

        # Trier la liste (pour cohérence)
        return sorted(value)

    def validate_jours_mois(self, value):
        """
        Validation de la liste des jours du mois:
        - Pas de doublons
        - Tri automatique
        - Au moins 1 jour si fourni
        """
        if value is None:
            return value

        if len(value) == 0:
            raise serializers.ValidationError(
                "Si vous spécifiez 'jours_mois', vous devez sélectionner au moins 1 jour"
            )

        # Vérifier les doublons
        if len(value) != len(set(value)):
            raise serializers.ValidationError(
                "La liste des jours contient des doublons"
            )

        # Trier la liste (pour cohérence)
        return sorted(value)

    def validate(self, data):
        """Validation globale de compatibilité"""
        frequence = data.get('frequence')
        jours_semaine = data.get('jours_semaine')
        jours_mois = data.get('jours_mois')

        # jours_semaine est uniquement compatible avec WEEKLY
        if jours_semaine and frequence != 'WEEKLY':
            raise serializers.ValidationError({
                'jours_semaine': f"La sélection de jours de semaine est uniquement disponible "
                                f"avec la fréquence WEEKLY (vous avez: {frequence})"
            })

        # jours_mois est uniquement compatible avec MONTHLY
        if jours_mois and frequence != 'MONTHLY':
            raise serializers.ValidationError({
                'jours_mois': f"La sélection de jours du mois est uniquement disponible "
                             f"avec la fréquence MONTHLY (vous avez: {frequence})"
            })

        # Ne pas permettre les deux en même temps
        if jours_semaine and jours_mois:
            raise serializers.ValidationError(
                "Vous ne pouvez pas spécifier à la fois 'jours_semaine' et 'jours_mois'"
            )

        return data


class DupliquerTacheDatesSpecifiquesSerializer(serializers.Serializer):
    """
    Serializer pour dupliquer une tâche à des dates spécifiques.
    """
    dates_cibles = serializers.ListField(
        child=serializers.DateField(),
        min_length=1,
        max_length=100,
        help_text="Liste des dates de début pour les nouvelles tâches (max 100)"
    )
    conserver_equipes = serializers.BooleanField(
        default=True,
        help_text="Conserver les équipes assignées"
    )
    conserver_objets = serializers.BooleanField(
        default=True,
        help_text="Conserver les objets liés (sites/inventaire)"
    )
    nouveau_statut = serializers.ChoiceField(
        choices=Tache.STATUT_CHOICES,
        default='PLANIFIEE',
        help_text="Statut des nouvelles tâches créées"
    )

    def validate_dates_cibles(self, value):
        """Valide que les dates sont dans l'ordre croissant."""
        dates_sorted = sorted(value)
        if dates_sorted != value:
            raise serializers.ValidationError(
                "Les dates doivent être fournies dans l'ordre chronologique"
            )
        return value


class TacheRecurrenceResponseSerializer(serializers.Serializer):
    """
    Serializer pour la réponse après duplication de tâches.
    """
    message = serializers.CharField()
    nombre_taches_creees = serializers.IntegerField()
    taches_creees = TacheSerializer(many=True)
    tache_source_id = serializers.IntegerField()



