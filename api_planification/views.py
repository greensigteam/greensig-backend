from datetime import datetime
import hashlib
import json
from django.db import models
from django.db.models.deletion import ProtectedError
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.cache import cache
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Tache, TypeTache, ParticipationTache, RatioProductivite, DistributionCharge

# Constantes pour le cache
CACHE_KEY_TACHES = 'taches_list_{user_id}_{params_hash}'
CACHE_TIMEOUT_TACHES = 60  # 1 minute
from .serializers import (
    TacheSerializer, TacheListSerializer, TacheCreateUpdateSerializer,
    TypeTacheSerializer, ParticipationTacheSerializer,
    RatioProductiviteSerializer, DistributionChargeSerializer,
    DistributionChargeEnrichedSerializer,
    DupliquerTacheSerializer, DupliquerTacheRecurrenceSerializer,
    DupliquerTacheDatesSpecifiquesSerializer, TacheRecurrenceResponseSerializer
)
from .services import WorkloadCalculationService
from django.utils import timezone
from .utils import (
    dupliquer_tache_avec_distributions,
    dupliquer_tache_recurrence_multiple,
    dupliquer_tache_recurrence_jours_semaine,
    dupliquer_tache_recurrence_jours_mois,
    dupliquer_tache_dates_specifiques,
    obtenir_frequences_compatibles,
    calculer_duree_tache
)
from rest_framework.pagination import PageNumberPagination
from api_users.mixins import RoleBasedQuerySetMixin, RoleBasedPermissionMixin
from api_users.permissions import IsAdmin, IsAdminOrReadOnly, IsSuperviseur, IsAdminOrSuperviseur

# Import des règles métier pour les distributions
from .business_rules import (
    valider_transition,
    valider_motif,
    valider_limite_reports,
    get_chaine_reports,
    synchroniser_tache_apres_demarrage,
    synchroniser_tache_apres_completion,
    synchroniser_tache_apres_annulation,
    synchroniser_tache_apres_restauration,
    etendre_tache_si_necessaire,
    verifier_premiere_distribution_active,
    verifier_equipe_assignee,
    verifier_date_disponible,
    # Validation de suppression des distributions
    valider_suppression_distribution,
    valider_suppression_distributions_bulk,
    synchroniser_tache_apres_suppression_distribution,
)
from .constants import MOTIFS_VALIDES, ERROR_MESSAGES


# ==============================================================================
# VIEWSET POUR LES DISTRIBUTIONS
# ==============================================================================
# ⚠️ SUPPRIMÉ: Ancienne version dupliquée (ligne 32-163)
# Voir la version complète avec RoleBasedQuerySetMixin à la ligne ~700


# ==============================================================================
# PAGINATION PERSONNALISÉE
# ==============================================================================

class SmallPageNumberPagination(PageNumberPagination):
    """Pagination avec 20 items par page pour les ressources système."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 500  # Augmenté pour permettre le chargement de tous les types de tâches


# ==============================================================================
# VIEWSETS
# ==============================================================================

class TypeTacheViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les types de tâches (ressource système).

    Permissions:
    - ADMIN: CRUD complet
    - SUPERVISEUR, CLIENT: Lecture seule

    Pagination: 20 items par page.
    """
    queryset = TypeTache.objects.all()
    serializer_class = TypeTacheSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = SmallPageNumberPagination

    @action(detail=False, methods=['get'])
    def applicables(self, request):
        """
        Retourne les types de tâches applicables à une liste de types d'objets.
        GET /api/planification/types-taches/applicables/?types_objets=Arbre,Gazon,Palmier

        Un type de tâche est applicable si un RatioProductivite existe
        pour TOUS les types d'objets fournis.
        """
        types_objets_param = request.query_params.get('types_objets', '')

        if not types_objets_param:
            # Si aucun type fourni, retourner tous les types de tâches
            serializer = self.get_serializer(self.get_queryset(), many=True)
            return Response(serializer.data)

        # Parser la liste des types d'objets (séparés par virgule)
        types_objets = [t.strip() for t in types_objets_param.split(',') if t.strip()]

        if not types_objets:
            serializer = self.get_serializer(self.get_queryset(), many=True)
            return Response(serializer.data)

        # Normaliser les noms de types (première lettre majuscule)
        types_objets_normalized = [t.capitalize() for t in types_objets]

        # Trouver les types de tâches qui ont un ratio pour TOUS les types d'objets
        from django.db.models import Count

        # Sous-requête: pour chaque type de tâche, compter combien des types demandés ont un ratio
        types_taches_applicables = TypeTache.objects.annotate(
            matching_ratios=Count(
                'ratios_productivite',
                filter=models.Q(
                    ratios_productivite__type_objet__in=types_objets_normalized,
                    ratios_productivite__actif=True
                )
            )
        ).filter(
            matching_ratios=len(types_objets_normalized)  # Doit matcher TOUS les types
        )

        serializer = self.get_serializer(types_taches_applicables, many=True)
        return Response({
            'types_objets_demandes': types_objets_normalized,
            'nombre_types_taches': len(serializer.data),
            'types_taches': serializer.data
        })

    @action(detail=True, methods=['get'])
    def objets_compatibles(self, request, pk=None):
        """
        Retourne les types d'objets compatibles avec ce type de tâche.
        GET /api/planification/types-taches/{id}/objets_compatibles/

        Un type d'objet est compatible s'il existe un RatioProductivite actif
        pour la combinaison (TypeTache, type_objet).
        """
        type_tache = self.get_object()

        # Récupérer tous les ratios actifs pour ce type de tâche
        ratios = RatioProductivite.objects.filter(
            id_type_tache=type_tache,
            actif=True
        ).values_list('type_objet', flat=True).distinct()

        types_objets_compatibles = list(ratios)

        return Response({
            'type_tache_id': type_tache.id,
            'type_tache_nom': type_tache.nom_tache,
            'nombre_types_objets': len(types_objets_compatibles),
            'types_objets_compatibles': types_objets_compatibles
        })

    def destroy(self, request, *args, **kwargs):
        """
        Supprime un type de tâche.

        Retourne une erreur 400 si des tâches existantes utilisent ce type
        (protection via foreign key PROTECT).
        """
        instance = self.get_object()
        try:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError as e:
            # Compter le nombre de tâches liées
            from .models import Tache
            taches_count = Tache.objects.filter(id_type_tache=instance).count()
            return Response(
                {
                    'error': 'protected_foreign_key',
                    'message': f'Impossible de supprimer ce type de tâche car {taches_count} tâche(s) existante(s) l\'utilisent.',
                    'detail': f'Le type "{instance.nom_tache}" est référencé par des tâches planifiées. Vous devez d\'abord supprimer ou modifier ces tâches.',
                    'taches_count': taches_count
                },
                status=status.HTTP_400_BAD_REQUEST
            )


class TacheViewSet(RoleBasedQuerySetMixin, RoleBasedPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet pour les tâches avec permissions automatiques via mixins.

    Permissions (via RoleBasedPermissionMixin):
    - ADMIN: CRUD complet + validation
    - SUPERVISEUR: CRUD sur les tâches de ses équipes (filtrage automatique)
    - CLIENT: Lecture seule sur les tâches de ses sites (filtrage automatique)

    Filtrage automatique: RoleBasedQuerySetMixin filtre selon le rôle
    Suppression: Suppression réelle (CASCADE sur distributions)
    """
    queryset = Tache.objects.all()
    serializer_class = TacheSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    # Permissions par action (RoleBasedPermissionMixin)
    permission_classes_by_action = {
        'create': [permissions.IsAuthenticated, IsAdminOrSuperviseur],
        'update': [permissions.IsAuthenticated, IsAdminOrSuperviseur],
        'partial_update': [permissions.IsAuthenticated, IsAdminOrSuperviseur],
        'destroy': [permissions.IsAuthenticated, IsAdminOrSuperviseur],
        'update_distributions': [permissions.IsAuthenticated, IsAdminOrSuperviseur],
        'valider': [permissions.IsAuthenticated, IsAdmin],
        'default': [permissions.IsAuthenticated],
    }

    def get_queryset(self):
        """
        Retourne le queryset des tâches avec filtrage automatique par rôle.

        Le filtrage par rôle est géré par RoleBasedQuerySetMixin:
        - ADMIN: Toutes les tâches
        - SUPERVISEUR: Tâches de ses équipes uniquement
        - CLIENT: Tâches de ses sites uniquement

        Note: La suppression est réelle (pas de soft delete).
        """
        from django.db.models import Q, Prefetch, Sum, Count
        from api_users.models import Equipe

        # Appeler le mixin pour filtrage par rôle + soft-delete
        qs = super().get_queryset()

        # ⚡ OPTIMISATION: Charger uniquement les relations essentielles pour la liste
        qs = qs.select_related(
            'id_client__utilisateur',
            'id_structure_client',
            'id_type_tache',
            'id_equipe',  # Simplifié: pas de chaîne profonde
            'reclamation',
            'reclamation__site'  # Pour site_id/site_nom fallback
        )

        # ⚡ PREFETCH MINIMAL: Seulement les infos utilisées par les serializers minimaux
        # ObjetMinimalSerializer: id, site_id, site_nom → besoin de 'objets__site' (only ID + nom)
        # EquipeMinimalSerializer: id, nom_equipe → aucun prefetch nécessaire
        qs = qs.prefetch_related(
            'equipes',  # Juste les IDs et noms (pas de relations supplémentaires)
            'objets__site',  # Site ID + nom seulement (via ObjetMinimalSerializer)
            'distributions_charge'  # ✅ Evite N+1 pour les distributions
        )

        # ⚡ ANNOTATIONS: Calculer les agrégations en une seule requête (pas N+1)
        # Note: Préfixe "_annot" pour éviter conflit avec les propriétés du modèle
        qs = qs.annotate(
            _annot_charge_totale=Sum('distributions_charge__heures_planifiees'),
            _annot_nombre_jours=Count('distributions_charge', filter=Q(distributions_charge__heures_planifiees__gt=0))
        )

        # Filtres optionnels via query params
        client_id = self.request.query_params.get('client_id')
        if client_id:
            qs = qs.filter(id_client=client_id)

        structure_client_id = self.request.query_params.get('structure_client_id')
        if structure_client_id:
            import logging
            logger = logging.getLogger(__name__)
            before_count = qs.count()
            qs = qs.filter(id_structure_client=structure_client_id)
            after_count = qs.count()
            logger.info(f"[TACHES] Filtre structure_client_id={structure_client_id}: {before_count} -> {after_count} taches")

        equipe_id = self.request.query_params.get('equipe_id')
        if equipe_id:
            qs = qs.filter(Q(equipes__id=equipe_id) | Q(id_equipe=equipe_id)).distinct()

        start_date = self.request.query_params.get('start_date')
        if start_date:
            qs = qs.filter(date_debut_planifiee__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            qs = qs.filter(date_fin_planifiee__lte=end_date)

        has_reclamation = self.request.query_params.get('has_reclamation')
        if has_reclamation == 'true':
            qs = qs.filter(reclamation__isnull=False)

        # Filtre par objet (pour afficher l'historique des tâches d'un objet)
        objet_id = self.request.query_params.get('objet_id')
        if objet_id:
            qs = qs.filter(objets__id=objet_id).distinct()

        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TacheCreateUpdateSerializer
        if self.action == 'list':
            return TacheListSerializer  # ⚡ Serializer optimisé pour la liste
        return TacheSerializer  # Serializer complet pour le détail

    def _get_cache_key(self, request):
        """Génère une clé de cache unique basée sur l'utilisateur, son rôle et les filtres."""
        user_id = request.user.id if request.user.is_authenticated else 'anon'
        # ⚡ SÉCURITÉ: Inclure le rôle dans la clé de cache pour éviter les fuites de données
        # Différents rôles voient différentes données (ADMIN: tout, CLIENT: ses sites uniquement)
        user_role = getattr(request.user, 'role', 'unknown') if request.user.is_authenticated else 'anon'
        # Hash des query params pour différencier les filtres
        params_str = json.dumps(dict(request.query_params), sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
        return f'taches_list_{user_id}_{user_role}_{params_hash}'

    def list(self, request, *args, **kwargs):
        """
        ⚡ Liste des tâches avec cache Redis (1 minute).

        Le cache est invalidé automatiquement par les tâches Celery
        quand des statuts changent.
        """
        cache_key = self._get_cache_key(request)

        # Essayer de récupérer depuis le cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        # Sinon, exécuter la requête normale
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        data = serializer.data

        # Mettre en cache
        cache.set(cache_key, data, CACHE_TIMEOUT_TACHES)

        return Response(data)

    def _invalidate_cache(self):
        """Invalide le cache après modification d'une tâche."""
        try:
            # Tenter de supprimer toutes les clés de cache des tâches
            cache.delete_pattern('greensig:taches_list_*')
        except (AttributeError, Exception):
            # Si delete_pattern n'est pas supporté, ignorer
            pass

    def perform_create(self, serializer):
        """Invalide le cache après création."""
        super().perform_create(serializer)
        self._invalidate_cache()

    def perform_update(self, serializer):
        """Invalide le cache après modification."""
        super().perform_update(serializer)
        self._invalidate_cache()

    def perform_destroy(self, instance):
        """Invalide le cache après suppression."""
        super().perform_destroy(instance)
        self._invalidate_cache()

    def update(self, request, *args, **kwargs):
        """Override update pour retourner une réponse minimale (sans _detail fields lourds)."""
        import time
        start = time.time()
        print(f"[VIEWSET] update() START")

        partial = kwargs.pop('partial', False)

        t1 = time.time()
        instance = self.get_object()
        print(f"[VIEWSET] get_object() took {time.time() - t1:.2f}s")

        t2 = time.time()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        print(f"[VIEWSET] get_serializer() took {time.time() - t2:.2f}s")

        t3 = time.time()
        serializer.is_valid(raise_exception=True)
        print(f"[VIEWSET] is_valid() took {time.time() - t3:.2f}s")

        t4 = time.time()
        self.perform_update(serializer)
        print(f"[VIEWSET] perform_update() took {time.time() - t4:.2f}s")

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        # ⚡ OPTIMISATION: Retourner une réponse minimale sans recharger tous les _detail
        # Le frontend rechargera les données via loadTaches() de toute façon
        print(f"[VIEWSET] update() TOTAL took {time.time() - start:.2f}s")
        return Response({
            'id': instance.id,
            'message': 'Tâche mise à jour avec succès'
        }, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        """Override partial_update pour utiliser la même optimisation."""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    # perform_destroy() utilise la suppression standard (CASCADE sur distributions)

    @action(detail=True, methods=['post'])
    def add_participation(self, request, pk=None):
        tache = self.get_object()
        # On force l'id_tache dans les données
        # ✅ FIX: Éviter .copy() sur un QueryDict (Multipart data) car il fait un deepcopy
        if hasattr(request.data, 'dict'):
            data = request.data.dict()
        else:
            data = request.data.copy() if hasattr(request.data, 'copy') else dict(request.data)
        data['id_tache'] = tache.id

        serializer = ParticipationTacheSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def reset_charge(self, request, pk=None):
        """
        Remet la tâche en mode calcul automatique et recalcule la charge.
        POST /api/planification/taches/{id}/reset_charge/
        """
        tache = self.get_object()
        charge, success = WorkloadCalculationService.reset_to_auto(tache)

        if success:
            return Response({
                'message': 'Charge recalculée automatiquement',
                'charge_estimee_heures': charge,
                'charge_manuelle': False
            })
        return Response(
            {'error': 'Erreur lors du recalcul de la charge'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    @action(detail=False, methods=['post'], url_path='refresh-task-statuses')
    def refresh_task_statuses(self, request):
        """
        DESACTIVEE: Endpoint conserve pour compatibilite.

        Le systeme simplifie ne calcule plus automatiquement les statuts
        EN_RETARD et EXPIREE. Les taches restent PLANIFIEE jusqu'a
        demarrage explicite par l'utilisateur.
        """
        return Response({
            'message': 'Endpoint desactive - systeme de statuts simplifie',
            'late_count': 0,
            'late_ids': [],
            'expired_count': 0,
            'expired_ids': [],
            'total_updated': 0
        })

    @action(detail=True, methods=['post'])
    def update_distributions(self, request, pk=None):
        """
        Met à jour les distributions de charge pour une tâche.
        POST /api/planification/taches/{id}/update_distributions/

        Body: {
            "distributions": [
                {
                    "date": "2024-01-15",
                    "heure_debut": "08:00",
                    "heure_fin": "17:00",
                    "commentaire": ""
                },
                ...
            ]
        }

        Cette action permet de sélectionner les jours de travail depuis le modal frontend
        et de créer automatiquement les distributions de charge correspondantes.

        Validations (via business_rules):
        - Tâche non terminée
        - Au moins une distribution fournie
        - Aucune distribution existante reportée

        Permission: IsAdmin ou IsSuperviseur
        """
        from django.core.exceptions import ValidationError as DjangoValidationError

        tache = self.get_object()
        distributions_data = request.data.get('distributions', [])

        if not isinstance(distributions_data, list):
            return Response(
                {'error': 'Le champ "distributions" doit être une liste'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validation: Au moins une distribution requise
        if len(distributions_data) == 0:
            return Response(
                {'error': 'Au moins une distribution est requise'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validation via les règles métier centralisées
        distributions_existantes = tache.distributions_charge.all()
        try:
            valider_suppression_distributions_bulk(
                tache=tache,
                distributions_a_supprimer=distributions_existantes,
                distributions_a_conserver=len(distributions_data)
            )
        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Supprimer les anciennes distributions (validations passées)
        distributions_existantes.delete()

        # Créer les nouvelles distributions
        created_distributions = []
        for dist_data in distributions_data:
            # Validation des champs requis
            if 'date' not in dist_data:
                return Response(
                    {'error': 'Chaque distribution doit avoir un champ "date"'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if 'heure_debut' not in dist_data or 'heure_fin' not in dist_data:
                return Response(
                    {'error': 'Chaque distribution doit avoir "heure_debut" et "heure_fin"'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculer les heures planifiées
            from datetime import datetime
            try:
                heure_debut = datetime.strptime(dist_data['heure_debut'], '%H:%M').time()
                heure_fin = datetime.strptime(dist_data['heure_fin'], '%H:%M').time()
            except ValueError:
                return Response(
                    {'error': 'Format d\'heure invalide. Utilisez HH:MM'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Créer la distribution via le serializer pour bénéficier de la validation
            serializer = DistributionChargeSerializer(data={
                'tache': tache.id,
                'date': dist_data['date'],
                'heure_debut': heure_debut,
                'heure_fin': heure_fin,
                'commentaire': dist_data.get('commentaire', '')
            })

            if serializer.is_valid():
                distribution = serializer.save()
                created_distributions.append(serializer.data)
            else:
                # Rollback: supprimer les distributions déjà créées
                for created in created_distributions:
                    DistributionCharge.objects.filter(id=created['id']).delete()

                return Response(
                    {'error': 'Erreur de validation', 'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Calculer le total des heures
        total_heures = sum(d['heures_planifiees'] for d in created_distributions)

        return Response({
            'message': f'{len(created_distributions)} distribution(s) créée(s) avec succès',
            'distributions': created_distributions,
            'total_heures': round(total_heures, 2),
            'nombre_jours': len(created_distributions)
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """
        Valide une tâche terminée (ADMIN uniquement).
        POST /api/planification/taches/{id}/valider/
        Body: { "etat": "VALIDEE" | "REJETEE", "commentaire": "..." }

        Permission: IsAdmin (définie dans permission_classes_by_action)
        """
        tache = self.get_object()

        # Vérifier que la tâche est terminée
        if tache.statut != 'TERMINEE':
            return Response(
                {'error': 'Seule une tâche terminée peut être validée ou rejetée'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupérer les données
        etat = request.data.get('etat')
        commentaire = request.data.get('commentaire', '')

        if etat not in ['VALIDEE', 'REJETEE']:
            return Response(
                {'error': "L'état doit être 'VALIDEE' ou 'REJETEE'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mettre à jour la tâche
        tache.etat_validation = etat
        tache.date_validation = timezone.now()
        tache.validee_par = request.user
        tache.commentaire_validation = commentaire
        tache.save(update_fields=['etat_validation', 'date_validation', 'validee_par', 'commentaire_validation'])

        # Envoyer notification
        from api.services.notifications import NotificationService
        NotificationService.notify_tache_validee(
            tache=tache,
            etat_validation=etat,
            valideur=request.user,
            commentaire=commentaire
        )

        # Préparer la réponse
        serializer = self.get_serializer(tache)
        response_data = {
            'message': f'Tâche {etat.lower()} avec succès',
            'tache': serializer.data
        }

        # Vérifier si la clôture de la réclamation peut être proposée
        # (uniquement si la tâche vient d'être validée et est liée à une réclamation)
        if etat == 'VALIDEE' and tache.reclamation:
            reclamation = tache.reclamation

            # Vérifier que la réclamation est dans un statut approprié
            if reclamation.statut in ['EN_COURS', 'RESOLUE']:
                # Récupérer toutes les tâches de cette réclamation
                taches_reclamation = reclamation.taches_correctives.all()

                # Vérifier si toutes les tâches sont terminées ET validées
                toutes_terminees = not taches_reclamation.exclude(statut='TERMINEE').exists()
                toutes_validees = not taches_reclamation.exclude(etat_validation='VALIDEE').exists()

                if toutes_terminees and toutes_validees:
                    response_data['proposition_cloture_possible'] = True
                    response_data['reclamation_id'] = reclamation.id
                    response_data['reclamation_numero'] = reclamation.numero_reclamation
                    response_data['nombre_taches_validees'] = taches_reclamation.count()

        return Response(response_data)

    @action(detail=True, methods=['post'], url_path='set-temps-travail-manuel')
    def set_temps_travail_manuel(self, request, pk=None):
        """
        Définit manuellement le temps de travail pour une tâche (OPTION 2: Approche Hybride).

        POST /api/planification/taches/{id}/set-temps-travail-manuel/
        Body: {
            "heures": 8.5  # Nombre d'heures (float)
        }

        Permission: IsAdmin ou IsSuperviseur

        Cette action permet de corriger manuellement le temps de travail calculé
        automatiquement. Le temps manuel a la priorité absolue sur tous les calculs
        automatiques.

        Pour réinitialiser le calcul automatique, envoyer null ou supprimer avec
        l'endpoint DELETE.
        """
        tache = self.get_object()

        # Vérifier que la tâche est terminée
        if tache.statut != 'TERMINEE':
            return Response(
                {'error': 'Seule une tâche terminée peut avoir un temps de travail manuel'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupérer les heures
        heures = request.data.get('heures')

        if heures is None:
            return Response(
                {'error': "Le champ 'heures' est requis"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Valider que heures est un nombre positif
        try:
            heures = float(heures)
            if heures < 0:
                return Response(
                    {'error': 'Le nombre d\'heures doit être positif ou zéro'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Le nombre d\'heures doit être un nombre valide'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mettre à jour la tâche
        tache.temps_travail_manuel = heures
        tache.temps_travail_manuel_par = request.user
        tache.temps_travail_manuel_date = timezone.now()
        tache.save(update_fields=['temps_travail_manuel', 'temps_travail_manuel_par', 'temps_travail_manuel_date'])

        # Récupérer le temps de travail calculé pour la réponse
        temps_travail = tache.temps_travail_total

        return Response({
            'message': 'Temps de travail manuel enregistré avec succès',
            'temps_travail_total': temps_travail
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path='reset-temps-travail-manuel')
    def reset_temps_travail_manuel(self, request, pk=None):
        """
        Réinitialise le temps de travail manuel et revient au calcul automatique.

        DELETE /api/planification/taches/{id}/reset-temps-travail-manuel/

        Permission: IsAdmin ou IsSuperviseur

        Supprime la correction manuelle et permet au système de recalculer
        automatiquement le temps de travail à partir des données disponibles
        (heures_reelles, participations, charge_estimee, etc.)
        """
        tache = self.get_object()

        # Réinitialiser les champs manuels
        tache.temps_travail_manuel = None
        tache.temps_travail_manuel_par = None
        tache.temps_travail_manuel_date = None
        tache.save(update_fields=['temps_travail_manuel', 'temps_travail_manuel_par', 'temps_travail_manuel_date'])

        # Récupérer le temps de travail recalculé
        temps_travail = tache.temps_travail_total

        return Response({
            'message': 'Temps de travail manuel réinitialisé (calcul automatique réactivé)',
            'temps_travail_total': temps_travail
        }, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        tache = serializer.save(_current_user=self.request.user)

        # Calcul automatique de la charge estimée
        WorkloadCalculationService.recalculate_and_save(tache)

        # Gestion Statut Réclamation (User 6.6.5.4)
        if tache.reclamation:
            from api_reclamations.models import HistoriqueReclamation
            
            rec = tache.reclamation
            # On passe en 'EN_COURS' uniquement si on est au début du cycle
            if rec.statut in ['NOUVELLE', 'PRISE_EN_COMPTE']:
                old_statut = rec.statut
                rec.statut = 'EN_COURS'
                rec.save()
                
                HistoriqueReclamation.objects.create(
                    reclamation=rec,
                    statut_precedent=old_statut,
                    statut_nouveau='EN_COURS',
                    auteur=self.request.user,
                    commentaire=f"Passage en cours automatique suite à la création de tâches"
                )

    @action(detail=True, methods=['post'], url_path='dupliquer-recurrence')
    def dupliquer_recurrence(self, request, pk=None):
        """
        Duplique une tâche selon une fréquence prédéfinie.

        ⚠️ ATTENTION (Option A): Si vous créez une tâche avec `recurrence_config`
        dans le POST initial, les occurrences sont DÉJÀ créées automatiquement.
        NE PAS appeler cet endpoint après pour éviter une double création!

        Cet endpoint est utile pour:
        - Dupliquer une tâche existante (créée sans récurrence)
        - Ajouter des occurrences supplémentaires
        - Tests manuels

        **Fréquences disponibles:**
        - `DAILY`: Quotidien (chaque jour)
        - `WEEKLY`: Hebdomadaire (chaque semaine, +7 jours)
        - `MONTHLY`: Mensuel (chaque mois, +30 jours)
        - `YEARLY`: Annuel (chaque année, +365 jours)

        **Exemple de requête:**
        ```json
        {
            "frequence": "WEEKLY",
            "nombre_occurrences": 12,
            "conserver_equipes": true,
            "conserver_objets": true,
            "nouveau_statut": "PLANIFIEE"
        }
        ```

        **Retourne:**
        - Liste des nouvelles tâches créées avec leurs distributions
        """
        tache = self.get_object()
        print(f"[API] dupliquer-recurrence appelé pour tâche #{tache.id}")
        print(f"[API] Données reçues: {request.data}")

        serializer = DupliquerTacheRecurrenceSerializer(data=request.data)

        if not serializer.is_valid():
            print(f"[API] Erreur validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        print(f"[API] Données validées: {serializer.validated_data}")

        try:
            # ✅ Détecter le mode de récurrence
            jours_semaine = serializer.validated_data.get('jours_semaine')
            jours_mois = serializer.validated_data.get('jours_mois')
            frequence = serializer.validated_data.get('frequence')

            if jours_semaine and frequence == 'WEEKLY':
                # Mode sélection de jours de la semaine (WEEKLY)
                print(f"[API] Mode sélection jours semaine: {jours_semaine}")
                nouvelles_taches = dupliquer_tache_recurrence_jours_semaine(
                    tache_id=tache.id,
                    jours_semaine=jours_semaine,
                    nombre_occurrences=serializer.validated_data.get('nombre_occurrences'),
                    date_fin_recurrence=serializer.validated_data.get('date_fin_recurrence'),
                    conserver_equipes=serializer.validated_data.get('conserver_equipes', True),
                    conserver_objets=serializer.validated_data.get('conserver_objets', True),
                    nouveau_statut=serializer.validated_data.get('nouveau_statut', 'PLANIFIEE')
                )
            elif jours_mois and frequence == 'MONTHLY':
                # Mode sélection de jours du mois (MONTHLY)
                print(f"[API] Mode sélection jours mois: {jours_mois}")
                nouvelles_taches = dupliquer_tache_recurrence_jours_mois(
                    tache_id=tache.id,
                    jours_mois=jours_mois,
                    nombre_occurrences=serializer.validated_data.get('nombre_occurrences'),
                    date_fin_recurrence=serializer.validated_data.get('date_fin_recurrence'),
                    conserver_equipes=serializer.validated_data.get('conserver_equipes', True),
                    conserver_objets=serializer.validated_data.get('conserver_objets', True),
                    nouveau_statut=serializer.validated_data.get('nouveau_statut', 'PLANIFIEE')
                )
            else:
                # Mode standard (décalage fixe)
                print(f"[API] Mode standard: fréquence {frequence}")
                nouvelles_taches = dupliquer_tache_recurrence_multiple(
                    tache_id=tache.id,
                    **serializer.validated_data
                )
            print(f"[API] {len(nouvelles_taches)} tâche(s) créée(s)")

            response_serializer = TacheRecurrenceResponseSerializer({
                'message': f'{len(nouvelles_taches)} tâche(s) récurrente(s) créée(s) avec succès',
                'nombre_taches_creees': len(nouvelles_taches),
                'taches_creees': nouvelles_taches,
                'tache_source_id': tache.id
            })

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except DjangoValidationError as e:
            print(f"[API] ValidationError: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            print(f"[API] ValueError: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"[API] Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Erreur lors de la création des récurrences: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='dupliquer-dates')
    def dupliquer_dates_specifiques(self, request, pk=None):
        """
        Duplique une tâche à des dates spécifiques.

        **Exemple de requête:**
        ```json
        {
            "dates_cibles": ["2026-02-15", "2026-03-15", "2026-04-15"],
            "conserver_equipes": true,
            "conserver_objets": true,
            "nouveau_statut": "PLANIFIEE"
        }
        ```

        **Notes:**
        - Les dates doivent être dans l'ordre chronologique
        - Les dates doivent être postérieures à la date de début de la tâche source
        - Maximum 100 dates

        **Retourne:**
        - Liste des nouvelles tâches créées avec leurs distributions
        """
        tache = self.get_object()
        serializer = DupliquerTacheDatesSpecifiquesSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            nouvelles_taches = dupliquer_tache_dates_specifiques(
                tache_id=tache.id,
                **serializer.validated_data
            )

            response_serializer = TacheRecurrenceResponseSerializer({
                'message': f'{len(nouvelles_taches)} tâche(s) créée(s) aux dates spécifiées',
                'nombre_taches_creees': len(nouvelles_taches),
                'taches_creees': nouvelles_taches,
                'tache_source_id': tache.id
            })

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la duplication aux dates spécifiques: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def perform_update(self, serializer):
        # Récupérer l'ancien statut avant la sauvegarde
        instance = self.get_object()
        ancien_statut = instance.statut if instance else None

        tache = serializer.save(_current_user=self.request.user)

        # Si le statut passe à TERMINEE, marquer toutes les distributions non réalisées comme réalisées
        if tache.statut == 'TERMINEE' and ancien_statut != 'TERMINEE':
            # Mettre à jour toutes les distributions qui ne sont pas encore réalisées
            distributions_non_realisees = tache.distributions_charge.filter(status='NON_REALISEE')
            nombre_mis_a_jour = distributions_non_realisees.update(status='REALISEE')

            if nombre_mis_a_jour > 0:
                print(f"✅ {nombre_mis_a_jour} distribution(s) marquée(s) comme réalisée(s) automatiquement")

        # Recalcul automatique de la charge estimée
        WorkloadCalculationService.recalculate_and_save(tache)


class RatioProductiviteViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour gérer les ratios de productivité (ressource système).
    Permet de définir les ratios par combinaison (type de tâche, type d'objet).

    Permissions:
    - ADMIN: CRUD complet
    - SUPERVISEUR, CLIENT: Lecture seule

    Pagination: 20 items par page.
    """
    queryset = RatioProductivite.objects.select_related('id_type_tache').all()
    serializer_class = RatioProductiviteSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]
    pagination_class = SmallPageNumberPagination

    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset()

        # Filtrer par type de tâche
        type_tache_id = self.request.query_params.get('type_tache_id')
        if type_tache_id:
            qs = qs.filter(id_type_tache_id=type_tache_id)

        # Filtrer par type d'objet
        type_objet = self.request.query_params.get('type_objet')
        if type_objet:
            qs = qs.filter(type_objet=type_objet)

        # Filtrer par statut actif
        actif = self.request.query_params.get('actif')
        if actif is not None:
            qs = qs.filter(actif=actif.lower() == 'true')

        # Recherche textuelle (type de tâche, type d'objet, description)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(id_type_tache__nom_tache__icontains=search) |
                Q(type_objet__icontains=search) |
                Q(description__icontains=search)
            )

        return qs


# ==============================================================================
# DISTRIBUTION DE CHARGE (TÂCHES MULTI-JOURS)
# ==============================================================================

class DistributionChargeViewSet(RoleBasedQuerySetMixin, viewsets.ModelViewSet):
    """
    ✅ API endpoint pour gérer les distributions de charge journalières.

    Permet de définir précisément la charge planifiée par jour pour des tâches
    s'étendant sur plusieurs jours.

    Permissions:
    - ADMIN: CRUD complet + voit toutes les distributions
    - SUPERVISEUR: CRUD pour les distributions des tâches sur ses sites
    - CLIENT: Lecture seule pour les distributions des tâches de sa structure

    Filtrage automatique (via RoleBasedQuerySetMixin):
    - ADMIN: Voit toutes les distributions
    - SUPERVISEUR: Voit uniquement les distributions des tâches sur ses sites
    - CLIENT: Voit uniquement les distributions des tâches de sa structure

    Filtres disponibles (via DistributionChargeFilter):
    - ?status=NON_REALISEE : Par statut
    - ?status__in=NON_REALISEE,EN_COURS : Plusieurs statuts
    - ?actif=true : Distributions actives (NON_REALISEE, EN_COURS)
    - ?date=2024-01-15 : Date exacte
    - ?date__gte=2024-01-01&date__lte=2024-01-31 : Periode
    - ?aujourd_hui=true : Distributions du jour
    - ?semaine_courante=true : Distributions de la semaine
    - ?tache=123 : Par tache
    - ?equipe=5 : Par equipe
    - ?site=10 : Par site
    - ?structure=3 : Par structure client
    - ?priorite__gte=4 : Par priorite de la tache
    - ?urgent=true : Taches urgentes (priorite >= 4)
    - ?type_tache__nom=elagage : Par type de tache
    - ?est_report=true : Distributions issues d'un report
    - ?search=keyword : Recherche textuelle
    - ?ordering=-date : Tri

    Exemples:
    - GET /api/planification/distributions/?status=NON_REALISEE&aujourd_hui=true
    - GET /api/planification/distributions/?equipe=5&actif=true
    - GET /api/planification/distributions/?site=10&date__gte=2024-01-01
    """
    from .filters import DistributionChargeFilter
    from django_filters.rest_framework import DjangoFilterBackend

    queryset = DistributionCharge.objects.select_related('tache').all()
    serializer_class = DistributionChargeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = DistributionChargeFilter

    def get_serializer_class(self):
        """
        Utilise le serializer enrichi pour les actions de lecture (list, retrieve)
        pour inclure les informations de la tâche associée.
        """
        if self.action in ['list', 'retrieve']:
            return DistributionChargeEnrichedSerializer
        return DistributionChargeSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Optimisation: prefetch les relations pour éviter N+1 queries
        qs = qs.select_related(
            'tache',
            'tache__id_type_tache',
        ).prefetch_related(
            'tache__equipes',
            'tache__objets__site'
        )
        return qs.order_by('date')

    def get_permissions(self):
        """
        Permissions adaptées par action:
        - ADMIN: Tout
        - SUPERVISEUR: CRUD pour ses équipes + actions de statut
        - CLIENT: Lecture seule uniquement (PAS d'actions de modification)
        """
        # Actions d'écriture (modification de statut)
        actions_ecriture = [
            'create', 'update', 'partial_update', 'destroy',
            'demarrer', 'terminer', 'reporter', 'annuler', 'restaurer',
            # Anciennes actions maintenues pour compatibilité
            'marquer_realisee', 'marquer_non_realisee'
        ]

        if self.action in actions_ecriture:
            # Écriture: ADMIN ou SUPERVISEUR uniquement (CLIENT refusé)
            permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperviseur]
        else:
            # Lecture (list, retrieve, historique): Tous authentifiés
            permission_classes = [permissions.IsAuthenticated]

        return [permission() for permission in permission_classes]

    def perform_update(self, serializer):
        """
        Validation supplémentaire lors de la mise à jour.
        Double couche de sécurité en plus de la validation du serializer.
        """
        distribution = self.get_object()
        tache = distribution.tache

        # Récupérer les nouvelles données (avec fallback sur les valeurs actuelles)
        new_date = serializer.validated_data.get('date', distribution.date)
        new_heure_debut = serializer.validated_data.get('heure_debut', distribution.heure_debut)
        new_heure_fin = serializer.validated_data.get('heure_fin', distribution.heure_fin)

        from rest_framework.exceptions import ValidationError
        from django.db import IntegrityError

        # Valider que la nouvelle date est dans la période de la tâche
        if new_date < tache.date_debut_planifiee or new_date > tache.date_fin_planifiee:
            raise ValidationError({
                'date': f"La date doit être comprise entre {tache.date_debut_planifiee} et {tache.date_fin_planifiee}"
            })

        # Valider que heure_fin > heure_debut
        if new_heure_debut and new_heure_fin:
            if new_heure_fin <= new_heure_debut:
                raise ValidationError({
                    'heure_fin': "L'heure de fin doit être postérieure à l'heure de début"
                })

        # Tenter la sauvegarde avec gestion de l'erreur d'unicité
        try:
            serializer.save()
        except IntegrityError as e:
            # Attraper l'erreur d'unicité de contrainte (tache, date)
            if 'tache_id_date' in str(e):
                raise ValidationError({
                    'date': f"Une distribution existe déjà pour cette tâche à la date du {new_date.strftime('%d/%m/%Y')}"
                })
            # Si c'est une autre erreur d'intégrité, la relancer
            raise

    def perform_create(self, serializer):
        """
        Validation lors de la création d'une distribution.

        Vérifie que :
        - La date est comprise entre la date de début et fin de la tâche
        - L'heure de fin est après l'heure de début
        - Pas de doublon (tache, date)
        """
        from rest_framework.exceptions import ValidationError
        from django.db import IntegrityError

        tache = serializer.validated_data.get('tache')
        date = serializer.validated_data.get('date')
        heure_debut = serializer.validated_data.get('heure_debut')
        heure_fin = serializer.validated_data.get('heure_fin')

        # Valider que la date est dans la période de la tâche
        if date < tache.date_debut_planifiee or date > tache.date_fin_planifiee:
            raise ValidationError({
                'date': f"La date doit être comprise entre {tache.date_debut_planifiee} et {tache.date_fin_planifiee}"
            })

        # Valider que heure_fin > heure_debut
        if heure_debut and heure_fin:
            if heure_fin <= heure_debut:
                raise ValidationError({
                    'heure_fin': "L'heure de fin doit être postérieure à l'heure de début"
                })

        # Tenter la sauvegarde avec gestion de l'erreur d'unicité
        try:
            serializer.save()
        except IntegrityError as e:
            # Attraper l'erreur d'unicité de contrainte (tache, date)
            if 'tache_id_date' in str(e):
                raise ValidationError({
                    'date': f"Une distribution existe déjà pour cette tâche à la date du {date.strftime('%d/%m/%Y')}"
                })
            # Si c'est une autre erreur d'intégrité, la relancer
            raise

    def perform_destroy(self, instance):
        """
        Validation et nettoyage lors de la suppression d'une distribution.

        Utilise les règles métier centralisées de business_rules.py:
        - valider_suppression_distribution()
        - synchroniser_tache_apres_suppression_distribution()
        """
        from rest_framework.exceptions import ValidationError
        from django.core.exceptions import ValidationError as DjangoValidationError

        tache = instance.tache

        # Valider la suppression via les règles métier centralisées
        try:
            valider_suppression_distribution(instance)
        except DjangoValidationError as e:
            raise ValidationError({'detail': str(e)})

        # Capturer l'état avant suppression pour synchronisation
        etait_en_cours = instance.status == 'EN_COURS'

        # Supprimer la distribution
        instance.delete()

        # Synchroniser le statut de la tâche
        synchroniser_tache_apres_suppression_distribution(tache, etait_en_cours)

    @action(detail=True, methods=['post'], url_path='marquer-realisee')
    def marquer_realisee(self, request, pk=None):
        """
        Marque une distribution de charge comme réalisée.
        POST /api/planification/distributions/{id}/marquer-realisee/

        Body (optionnel):
        {
            "heures_reelles": 7.5  // Heures réellement travaillées
        }

        Logique automatique:
        - Si c'est la premiere distribution marquee comme realisee
        - Et que la tache est en statut PLANIFIEE
        - Alors:
          * La tache passe automatiquement en statut EN_COURS
          * La date_debut_reelle de la tache est definie avec la date actuelle
        """
        distribution = self.get_object()
        tache = distribution.tache

        # Vérifier si c'est la première distribution réalisée
        nombre_distributions_realisees = tache.distributions_charge.filter(status='REALISEE').count()
        est_premiere_distribution = nombre_distributions_realisees == 0

        # Mettre à jour le statut de la distribution
        distribution.status = 'REALISEE'

        # Optionnellement, enregistrer les heures réelles
        heures_reelles = request.data.get('heures_reelles')
        if heures_reelles is not None:
            distribution.heures_reelles = heures_reelles

        distribution.save()

        # Si c'est la première distribution réalisée et que la tâche est PLANIFIEE,
        # passer la tâche en EN_COURS et définir la date de début réelle
        if est_premiere_distribution and tache.statut == 'PLANIFIEE':
            tache.statut = 'EN_COURS'
            tache.date_debut_reelle = timezone.now().date()  # Date actuelle (aujourd'hui)
            tache.save()

        serializer = self.get_serializer(distribution)
        return Response({
            'message': 'Distribution marquée comme réalisée',
            'distribution': serializer.data,
            'tache_statut_modifie': tache.statut == 'EN_COURS',  # Après modification
            'date_debut_reelle_definie': tache.date_debut_reelle is not None
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='marquer-non-realisee')
    def marquer_non_realisee(self, request, pk=None):
        """
        Marque une distribution comme non réalisée (la remet en statut NON_REALISEE).
        POST /api/planification/distributions/{id}/marquer-non-realisee/

        Logique automatique:
        - Si c'etait la derniere distribution realisee
        - Et que la tache est en statut EN_COURS
        - Alors:
          * La tache repasse en PLANIFIEE
          * La date_debut_reelle de la tache est supprimee (remise a None)
        """
        distribution = self.get_object()
        tache = distribution.tache

        if distribution.status != 'REALISEE':
            return Response({
                'error': 'Seules les distributions réalisées peuvent être marquées comme non réalisées'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Vérifier si c'est la dernière distribution réalisée
        nombre_distributions_realisees = tache.distributions_charge.filter(status='REALISEE').count()
        est_derniere_distribution = nombre_distributions_realisees == 1

        distribution.status = 'NON_REALISEE'
        distribution.save()

        # Si c'était la dernière distribution réalisée et que la tâche est EN_COURS,
        # remettre la tâche en PLANIFIEE
        # et supprimer la date de début réelle
        nouveau_statut = None
        if est_derniere_distribution and tache.statut == 'EN_COURS':
            tache.date_debut_reelle = None

            # Remettre la tâche en PLANIFIEE
            tache.statut = 'PLANIFIEE'
            nouveau_statut = 'PLANIFIEE'
            tache.save()

        serializer = self.get_serializer(distribution)
        return Response({
            'message': 'Distribution marquée comme non réalisée',
            'distribution': serializer.data,
            'tache_statut_modifie': nouveau_statut is not None,
            'nouveau_statut': nouveau_statut,
            'date_debut_reelle_supprimee': tache.date_debut_reelle is None
        }, status=status.HTTP_200_OK)

    # ==========================================================================
    # NOUVELLES ACTIONS - SYSTÈME DE STATUTS AVANCÉ
    # ==========================================================================

    @action(detail=True, methods=['post'], url_path='demarrer')
    def demarrer(self, request, pk=None):
        """
        Démarre une distribution de charge (NON_REALISEE → EN_COURS).

        POST /api/planification/distributions/{id}/demarrer/

        Body (optionnel):
        {
            "heure_debut_reelle": "08:00",    // Heure réelle de début (terrain)
            "date_debut_reelle": "2024-01-15" // Date réelle de début de la tâche
        }

        Transitions autorisées:
        - NON_REALISEE → EN_COURS

        Impossible de demarrer avant la date planifiee.

        Effets sur la tâche mère:
        - Si c'est la première distribution démarrée et que la tâche est
          PLANIFIEE, la tâche passe en EN_COURS.
        - date_debut_reelle est définie sur la tâche (avec la date fournie ou aujourd'hui).
        """
        from rest_framework.exceptions import ValidationError
        from datetime import datetime

        distribution = self.get_object()
        tache = distribution.tache
        ancien_statut = distribution.status

        # Vérifier qu'une équipe est assignée à la tâche
        if not verifier_equipe_assignee(tache):
            raise ValidationError({
                'detail': "Impossible de démarrer cette distribution : aucune équipe n'est assignée à la tâche. "
                          "Veuillez d'abord assigner une équipe."
            })

        # Impossible de démarrer avant la date planifiée
        today = timezone.now().date()
        if distribution.date > today:
            raise ValidationError({
                'detail': f"Impossible de démarrer cette distribution avant sa date planifiée ({distribution.date}). "
                          f"La date actuelle est {today}."
            })

        # Valider la transition
        try:
            valider_transition(ancien_statut, 'EN_COURS')
        except DjangoValidationError as e:
            raise ValidationError({'detail': str(e)})

        # Vérifier si c'est la première distribution active
        est_premiere = verifier_premiere_distribution_active(tache)

        # Mettre à jour la distribution
        distribution.status = 'EN_COURS'
        distribution.date_demarrage = timezone.now()

        # Enregistrer l'heure réelle de début (optionnel)
        heure_debut_reelle = request.data.get('heure_debut_reelle')
        if heure_debut_reelle:
            try:
                distribution.heure_debut_reelle = datetime.strptime(heure_debut_reelle, '%H:%M').time()
            except ValueError:
                try:
                    distribution.heure_debut_reelle = datetime.strptime(heure_debut_reelle, '%H:%M:%S').time()
                except ValueError:
                    raise ValidationError({'heure_debut_reelle': 'Format invalide. Utilisez HH:MM ou HH:MM:SS'})

        distribution.save()

        # Extraire la date réelle de début (optionnel)
        date_debut_reelle = None
        date_debut_reelle_str = request.data.get('date_debut_reelle')
        if date_debut_reelle_str:
            try:
                date_debut_reelle = datetime.strptime(date_debut_reelle_str, '%Y-%m-%d').date()
            except ValueError:
                raise ValidationError({'date_debut_reelle': 'Format invalide. Utilisez YYYY-MM-DD'})

        # Synchroniser la tâche mère (avec la date réelle si fournie)
        tache_modifiee = synchroniser_tache_apres_demarrage(tache, est_premiere, date_debut_reelle)

        serializer = self.get_serializer(distribution)
        return Response({
            'message': 'Distribution démarrée avec succès',
            'distribution': serializer.data,
            'ancien_statut': ancien_statut,
            'nouveau_statut': 'EN_COURS',
            'tache_synchronisee': tache_modifiee,
            'tache_nouveau_statut': tache.statut if tache_modifiee else None
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='terminer')
    def terminer(self, request, pk=None):
        """
        Termine une distribution de charge (EN_COURS → REALISEE).

        POST /api/planification/distributions/{id}/terminer/

        Body (optionnel):
        {
            "heure_debut_reelle": "08:00",  // Heure réelle de début (terrain)
            "heure_fin_reelle": "12:30",    // Heure réelle de fin (terrain)
            "heures_reelles": 4.5,          // Override manuel (sinon auto-calculé)
            "date_fin_reelle": "2024-01-15" // Date réelle de fin de la tâche
        }

        Transitions autorisées:
        - EN_COURS → REALISEE

        Effets sur la tâche mère:
        - Si toutes les distributions sont terminées (REALISEE/ANNULEE),
          la tâche passe en TERMINEE avec la date_fin_reelle fournie ou aujourd'hui.
        """
        from rest_framework.exceptions import ValidationError
        from datetime import datetime

        distribution = self.get_object()
        tache = distribution.tache
        ancien_statut = distribution.status

        # Valider la transition
        try:
            valider_transition(ancien_statut, 'REALISEE')
        except DjangoValidationError as e:
            raise ValidationError({'detail': str(e)})

        # Mettre à jour la distribution
        distribution.status = 'REALISEE'
        distribution.date_completion = timezone.now()

        # Enregistrer les heures réelles de terrain (optionnel)
        heure_debut_reelle = request.data.get('heure_debut_reelle')
        heure_fin_reelle = request.data.get('heure_fin_reelle')

        if heure_debut_reelle:
            try:
                distribution.heure_debut_reelle = datetime.strptime(heure_debut_reelle, '%H:%M').time()
            except ValueError:
                try:
                    distribution.heure_debut_reelle = datetime.strptime(heure_debut_reelle, '%H:%M:%S').time()
                except ValueError:
                    raise ValidationError({'heure_debut_reelle': 'Format invalide. Utilisez HH:MM ou HH:MM:SS'})

        if heure_fin_reelle:
            try:
                distribution.heure_fin_reelle = datetime.strptime(heure_fin_reelle, '%H:%M').time()
            except ValueError:
                try:
                    distribution.heure_fin_reelle = datetime.strptime(heure_fin_reelle, '%H:%M:%S').time()
                except ValueError:
                    raise ValidationError({'heure_fin_reelle': 'Format invalide. Utilisez HH:MM ou HH:MM:SS'})

        # Validation: heure_fin_reelle > heure_debut_reelle
        if distribution.heure_debut_reelle and distribution.heure_fin_reelle:
            if distribution.heure_fin_reelle <= distribution.heure_debut_reelle:
                raise ValidationError({
                    'heure_fin_reelle': "L'heure de fin réelle doit être postérieure à l'heure de début réelle"
                })

        # Heures réelles: override manuel ou auto-calculé dans save()
        heures_reelles = request.data.get('heures_reelles')
        if heures_reelles is not None:
            try:
                distribution.heures_reelles = float(heures_reelles)
            except (ValueError, TypeError):
                raise ValidationError({'heures_reelles': 'Doit être un nombre valide'})

        distribution.save()

        # Extraire la date réelle de fin (optionnel)
        date_fin_reelle = None
        date_fin_reelle_str = request.data.get('date_fin_reelle')
        if date_fin_reelle_str:
            try:
                date_fin_reelle = datetime.strptime(date_fin_reelle_str, '%Y-%m-%d').date()
            except ValueError:
                raise ValidationError({'date_fin_reelle': 'Format invalide. Utilisez YYYY-MM-DD'})

        # Synchroniser la tâche mère (avec la date réelle si fournie)
        tache_modifiee = synchroniser_tache_apres_completion(tache, date_fin_reelle)

        serializer = self.get_serializer(distribution)
        return Response({
            'message': 'Distribution terminée avec succès',
            'distribution': serializer.data,
            'ancien_statut': ancien_statut,
            'nouveau_statut': 'REALISEE',
            'tache_synchronisee': tache_modifiee,
            'tache_nouveau_statut': tache.statut if tache_modifiee else None
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reporter')
    def reporter(self, request, pk=None):
        """
        Reporte une distribution à une nouvelle date (→ REPORTEE + nouvelle distribution).

        POST /api/planification/distributions/{id}/reporter/

        Body:
        {
            "nouvelle_date": "2026-02-15",
            "motif": "METEO",  // METEO, ABSENCE, EQUIPEMENT, CLIENT, URGENCE, AUTRE
            "commentaire": "Pluie intense prévue"  // Optionnel
        }

        Transitions autorisees:
        - NON_REALISEE -> REPORTEE

        Règles:
        - La nouvelle date doit être dans le futur
        - Maximum 5 reports chaînés
        - Une nouvelle distribution est créée automatiquement
        - Les deux distributions sont liées (distribution_origine ↔ distribution_remplacement)

        Effets sur la tâche mère:
        - La date de fin peut être étendue si la nouvelle date dépasse
        """
        from rest_framework.exceptions import ValidationError
        from datetime import datetime

        distribution = self.get_object()
        tache = distribution.tache
        ancien_statut = distribution.status

        # Récupérer les données
        nouvelle_date_str = request.data.get('nouvelle_date')
        motif = request.data.get('motif')
        commentaire = request.data.get('commentaire', '')

        # Validations
        if not nouvelle_date_str:
            raise ValidationError({'nouvelle_date': 'La nouvelle date est requise'})

        try:
            nouvelle_date = datetime.strptime(nouvelle_date_str, '%Y-%m-%d').date()
        except ValueError:
            raise ValidationError({'nouvelle_date': 'Format de date invalide (YYYY-MM-DD)'})

        # Valider que la date est dans le futur
        if nouvelle_date <= timezone.now().date():
            raise ValidationError({'nouvelle_date': ERROR_MESSAGES['date_future_required']})

        # Valider le motif
        try:
            valider_motif(motif, obligatoire=True)
        except DjangoValidationError as e:
            raise ValidationError({'motif': str(e)})

        # Valider la transition
        try:
            valider_transition(ancien_statut, 'REPORTEE')
        except DjangoValidationError as e:
            raise ValidationError({'detail': str(e)})

        # Valider la limite de reports
        try:
            nombre_reports = valider_limite_reports(distribution)
        except DjangoValidationError as e:
            raise ValidationError({'detail': str(e)})

        # Vérifier que la date n'est pas déjà utilisée
        if not verifier_date_disponible(tache, nouvelle_date):
            raise ValidationError({
                'nouvelle_date': ERROR_MESSAGES['date_conflict'].format(
                    date=nouvelle_date.strftime('%d/%m/%Y')
                )
            })

        # Créer la nouvelle distribution
        nouvelle_distribution = DistributionCharge.objects.create(
            tache=tache,
            date=nouvelle_date,
            heures_planifiees=distribution.heures_planifiees,
            heure_debut=distribution.heure_debut,
            heure_fin=distribution.heure_fin,
            commentaire=f"Report de {distribution.date.strftime('%d/%m/%Y')} - {commentaire}".strip(),
            status='NON_REALISEE',
            distribution_origine=distribution
        )

        # Mettre à jour la distribution originale
        distribution.status = 'REPORTEE'
        distribution.motif_report_annulation = motif
        distribution.commentaire = commentaire or distribution.commentaire
        distribution.distribution_remplacement = nouvelle_distribution
        distribution.save()

        # Étendre la tâche si nécessaire
        tache_etendue = etendre_tache_si_necessaire(tache, nouvelle_date)

        serializer = self.get_serializer(distribution)
        nouvelle_serializer = self.get_serializer(nouvelle_distribution)

        return Response({
            'message': f'Distribution reportée au {nouvelle_date.strftime("%d/%m/%Y")}',
            'distribution_originale': serializer.data,
            'nouvelle_distribution': nouvelle_serializer.data,
            'ancien_statut': ancien_statut,
            'motif': motif,
            'nombre_reports_chaine': nombre_reports + 1,
            'tache_etendue': tache_etendue
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='annuler')
    def annuler(self, request, pk=None):
        """
        Annule une distribution de charge (→ ANNULEE).

        POST /api/planification/distributions/{id}/annuler/

        Body:
        {
            "motif": "CLIENT",  // METEO, ABSENCE, EQUIPEMENT, CLIENT, URGENCE, AUTRE
            "commentaire": "Client a annulé la prestation"  // Optionnel
        }

        Transitions autorisees:
        - NON_REALISEE -> ANNULEE
        - EN_COURS -> ANNULEE

        Effets sur la tâche mère:
        - Si toutes les distributions sont ANNULEE → Tâche ANNULEE
        - Si certaines REALISEE, reste ANNULEE → Tâche TERMINEE
        - Si plus de distributions actives et aucune réalisée → PLANIFIEE
        """
        from rest_framework.exceptions import ValidationError

        distribution = self.get_object()
        tache = distribution.tache
        ancien_statut = distribution.status

        # Récupérer les données
        motif = request.data.get('motif')
        commentaire = request.data.get('commentaire', '')

        # Valider le motif
        try:
            valider_motif(motif, obligatoire=True)
        except DjangoValidationError as e:
            raise ValidationError({'motif': str(e)})

        # Valider la transition
        try:
            valider_transition(ancien_statut, 'ANNULEE')
        except DjangoValidationError as e:
            raise ValidationError({'detail': str(e)})

        # Mettre à jour la distribution
        distribution.status = 'ANNULEE'
        distribution.motif_report_annulation = motif
        distribution.commentaire = commentaire or distribution.commentaire
        distribution.save()

        # Synchroniser la tâche mère
        tache_modifiee, nouveau_statut_tache = synchroniser_tache_apres_annulation(tache)

        serializer = self.get_serializer(distribution)
        return Response({
            'message': 'Distribution annulée',
            'distribution': serializer.data,
            'ancien_statut': ancien_statut,
            'nouveau_statut': 'ANNULEE',
            'motif': motif,
            'tache_synchronisee': tache_modifiee,
            'tache_nouveau_statut': nouveau_statut_tache if tache_modifiee else None
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='restaurer')
    def restaurer(self, request, pk=None):
        """
        Restaure une distribution annulée (ANNULEE → NON_REALISEE).

        POST /api/planification/distributions/{id}/restaurer/

        Transitions autorisées:
        - ANNULEE → NON_REALISEE

        Effets sur la tache mere:
        - Si la tache etait ANNULEE, elle repasse en PLANIFIEE
        """
        from rest_framework.exceptions import ValidationError

        distribution = self.get_object()
        tache = distribution.tache
        ancien_statut = distribution.status

        # Valider la transition
        try:
            valider_transition(ancien_statut, 'NON_REALISEE')
        except DjangoValidationError as e:
            raise ValidationError({'detail': str(e)})

        # Mettre à jour la distribution
        distribution.status = 'NON_REALISEE'
        distribution.motif_report_annulation = ''  # Vider le motif (chaîne vide, pas None)
        distribution.save()

        # Synchroniser la tâche mère
        tache_modifiee, nouveau_statut_tache = synchroniser_tache_apres_restauration(tache)

        serializer = self.get_serializer(distribution)
        return Response({
            'message': 'Distribution restaurée',
            'distribution': serializer.data,
            'ancien_statut': ancien_statut,
            'nouveau_statut': 'NON_REALISEE',
            'tache_synchronisee': tache_modifiee,
            'tache_nouveau_statut': nouveau_statut_tache if tache_modifiee else None
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='par-jour')
    def par_jour(self, request):
        """
        Retourne les distributions pour une date donnée avec les détails des tâches.

        GET /api/planification/distributions/par-jour/?date=2024-01-15

        Paramètres:
        - date (requis): Date au format YYYY-MM-DD

        Retourne:
        - Liste des distributions pour cette date
        - Chaque distribution inclut les informations de sa tâche associée
        - Trié par heure de début
        """
        date = request.query_params.get('date')

        if not date:
            return Response(
                {'error': "Le paramètre 'date' est requis (format YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupérer les distributions avec filtrage par rôle (via get_queryset)
        qs = self.get_queryset().filter(date=date)

        # Optimisation: prefetch les relations pour éviter N+1
        qs = qs.select_related(
            'tache',
            'tache__id_type_tache',
        ).prefetch_related(
            'tache__equipes',
            'tache__objets__site'
        ).order_by('heure_debut', 'tache__reference')

        # Utiliser le serializer enrichi
        serializer = DistributionChargeEnrichedSerializer(qs, many=True)

        # Calculs statistiques
        stats = {
            'total': qs.count(),
            'par_statut': {},
            'heures_planifiees_total': 0
        }

        for d in qs:
            status_key = d.status or 'NON_REALISEE'
            stats['par_statut'][status_key] = stats['par_statut'].get(status_key, 0) + 1
            stats['heures_planifiees_total'] += d.heures_planifiees or 0

        return Response({
            'date': date,
            'distributions': serializer.data,
            'statistiques': stats
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='historique')
    def historique(self, request, pk=None):
        """
        Retourne l'historique complet des reports pour une distribution.

        GET /api/planification/distributions/{id}/historique/

        Retourne:
        - La chaîne complète des distributions liées par reports
        - De l'origine jusqu'à la distribution finale
        - Avec tous les motifs et dates intermédiaires
        """
        distribution = self.get_object()

        # Récupérer la chaîne de reports
        chaine = get_chaine_reports(distribution)

        return Response({
            'distribution_id': distribution.id,
            'nombre_reports': len(chaine) - 1,  # -1 car l'origine n'est pas un report
            'chaine_reports': chaine,
            'distribution_origine_id': chaine[0]['id'] if chaine else None,
            'distribution_finale_id': chaine[-1]['id'] if chaine else None
        }, status=status.HTTP_200_OK)


class TacheRecurrenceViewSet(RoleBasedQuerySetMixin, viewsets.ModelViewSet):
    """
    ⚠️ RENOMMÉ: Ancien TacheViewSet pour éviter collision avec le TacheViewSet principal (ligne 140)

    ViewSet pour les tâches avec fonctionnalité de récurrence/duplication.

    Filtrage automatique (via RoleBasedQuerySetMixin):
    - ADMIN: Toutes les tâches
    - SUPERVISEUR: Tâches sur ses sites uniquement
    - CLIENT: Tâches de sa structure uniquement
    """
    queryset = Tache.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'create' or self.action == 'update':
            return TacheCreateUpdateSerializer
        return TacheSerializer

    @action(detail=True, methods=['post'], url_path='dupliquer')
    def dupliquer(self, request, pk=None):
        """
        Duplique une tâche avec décalage personnalisé.

        **Exemple de requête:**
        ```json
        {
            "decalage_jours": 7,
            "nombre_occurrences": 4,
            "conserver_equipes": true,
            "conserver_objets": true,
            "nouveau_statut": "PLANIFIEE"
        }
        ```

        **Retourne:**
        - Liste des nouvelles tâches créées avec leurs distributions
        """
        tache = self.get_object()
        print(f"[API] dupliquer appelé pour tâche #{tache.id}")
        print(f"[API] Données reçues: {request.data}")

        serializer = DupliquerTacheSerializer(data=request.data)

        if not serializer.is_valid():
            print(f"[API] Erreur validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        print(f"[API] Données validées: {serializer.validated_data}")

        try:
            nouvelles_taches = dupliquer_tache_avec_distributions(
                tache_id=tache.id,
                **serializer.validated_data
            )
            print(f"[API] {len(nouvelles_taches)} tâche(s) créée(s)")

            response_serializer = TacheRecurrenceResponseSerializer({
                'message': f'{len(nouvelles_taches)} tâche(s) créée(s) avec succès',
                'nombre_taches_creees': len(nouvelles_taches),
                'taches_creees': nouvelles_taches,
                'tache_source_id': tache.id
            })

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except DjangoValidationError as e:
            print(f"[API] ValidationError: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            print(f"[API] ValueError: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"[API] Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Erreur lors de la duplication: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='dupliquer-recurrence')
    def dupliquer_recurrence(self, request, pk=None):
        """
        Duplique une tâche selon une fréquence prédéfinie.

        ⚠️ ATTENTION (Option A): Si vous créez une tâche avec `recurrence_config`
        dans le POST initial, les occurrences sont DÉJÀ créées automatiquement.
        NE PAS appeler cet endpoint après pour éviter une double création!

        Cet endpoint est utile pour:
        - Dupliquer une tâche existante (créée sans récurrence)
        - Ajouter des occurrences supplémentaires
        - Tests manuels

        **Fréquences disponibles:**
        - `DAILY`: Quotidien (chaque jour)
        - `WEEKLY`: Hebdomadaire (chaque semaine, +7 jours)
        - `MONTHLY`: Mensuel (chaque mois, +30 jours)
        - `YEARLY`: Annuel (chaque année, +365 jours)

        **Exemple de requête:**
        ```json
        {
            "frequence": "WEEKLY",
            "nombre_occurrences": 12,
            "conserver_equipes": true,
            "conserver_objets": true,
            "nouveau_statut": "PLANIFIEE"
        }
        ```

        **Retourne:**
        - Liste des nouvelles tâches créées avec leurs distributions
        """
        tache = self.get_object()
        print(f"[API] dupliquer-recurrence appelé pour tâche #{tache.id}")
        print(f"[API] Données reçues: {request.data}")

        serializer = DupliquerTacheRecurrenceSerializer(data=request.data)

        if not serializer.is_valid():
            print(f"[API] Erreur validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        print(f"[API] Données validées: {serializer.validated_data}")

        try:
            # ✅ Détecter le mode de récurrence
            jours_semaine = serializer.validated_data.get('jours_semaine')
            jours_mois = serializer.validated_data.get('jours_mois')
            frequence = serializer.validated_data.get('frequence')

            if jours_semaine and frequence == 'WEEKLY':
                # Mode sélection de jours de la semaine (WEEKLY)
                print(f"[API] Mode sélection jours semaine: {jours_semaine}")
                nouvelles_taches = dupliquer_tache_recurrence_jours_semaine(
                    tache_id=tache.id,
                    jours_semaine=jours_semaine,
                    nombre_occurrences=serializer.validated_data.get('nombre_occurrences'),
                    date_fin_recurrence=serializer.validated_data.get('date_fin_recurrence'),
                    conserver_equipes=serializer.validated_data.get('conserver_equipes', True),
                    conserver_objets=serializer.validated_data.get('conserver_objets', True),
                    nouveau_statut=serializer.validated_data.get('nouveau_statut', 'PLANIFIEE')
                )
            elif jours_mois and frequence == 'MONTHLY':
                # Mode sélection de jours du mois (MONTHLY)
                print(f"[API] Mode sélection jours mois: {jours_mois}")
                nouvelles_taches = dupliquer_tache_recurrence_jours_mois(
                    tache_id=tache.id,
                    jours_mois=jours_mois,
                    nombre_occurrences=serializer.validated_data.get('nombre_occurrences'),
                    date_fin_recurrence=serializer.validated_data.get('date_fin_recurrence'),
                    conserver_equipes=serializer.validated_data.get('conserver_equipes', True),
                    conserver_objets=serializer.validated_data.get('conserver_objets', True),
                    nouveau_statut=serializer.validated_data.get('nouveau_statut', 'PLANIFIEE')
                )
            else:
                # Mode standard (décalage fixe)
                print(f"[API] Mode standard: fréquence {frequence}")
                nouvelles_taches = dupliquer_tache_recurrence_multiple(
                    tache_id=tache.id,
                    **serializer.validated_data
                )
            print(f"[API] {len(nouvelles_taches)} tâche(s) créée(s)")

            response_serializer = TacheRecurrenceResponseSerializer({
                'message': f'{len(nouvelles_taches)} tâche(s) récurrente(s) créée(s) avec succès',
                'nombre_taches_creees': len(nouvelles_taches),
                'taches_creees': nouvelles_taches,
                'tache_source_id': tache.id
            })

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except DjangoValidationError as e:
            print(f"[API] ValidationError: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            print(f"[API] ValueError: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"[API] Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Erreur lors de la création des récurrences: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'], url_path='dupliquer-dates')
    def dupliquer_dates_specifiques(self, request, pk=None):
        """
        Duplique une tâche à des dates spécifiques.

        **Exemple de requête:**
        ```json
        {
            "dates_cibles": ["2026-02-15", "2026-03-15", "2026-04-15"],
            "conserver_equipes": true,
            "conserver_objets": true,
            "nouveau_statut": "PLANIFIEE"
        }
        ```

        **Notes:**
        - Les dates doivent être dans l'ordre chronologique
        - Les dates doivent être postérieures à la date de début de la tâche source
        - Maximum 100 dates

        **Retourne:**
        - Liste des nouvelles tâches créées avec leurs distributions
        """
        tache = self.get_object()
        serializer = DupliquerTacheDatesSpecifiquesSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            nouvelles_taches = dupliquer_tache_dates_specifiques(
                tache_id=tache.id,
                **serializer.validated_data
            )

            response_serializer = TacheRecurrenceResponseSerializer({
                'message': f'{len(nouvelles_taches)} tâche(s) créée(s) aux dates spécifiées',
                'nombre_taches_creees': len(nouvelles_taches),
                'taches_creees': nouvelles_taches,
                'tache_source_id': tache.id
            })

            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': f'Erreur lors de la duplication aux dates spécifiques: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='frequences-compatibles')
    def frequences_compatibles(self, request, pk=None):
        """
        Retourne les fréquences de récurrence compatibles avec la durée de la tâche.

        **Utilisation:**
        Appelez cet endpoint AVANT de créer une récurrence pour afficher
        seulement les options valides à l'utilisateur.

        **Règle de compatibilité:**
        Le décalage de la fréquence doit être >= durée de la tâche
        pour éviter le chevauchement des occurrences.

        **Exemples de réponse:**

        Tâche de 1 jour:
        ```json
        {
            "duree_tache_jours": 1,
            "date_debut": "2026-01-14",
            "date_fin": "2026-01-14",
            "frequences_compatibles": ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"],
            "frequences_incompatibles": []
        }
        ```

        Tâche de 10 jours:
        ```json
        {
            "duree_tache_jours": 10,
            "date_debut": "2026-01-14",
            "date_fin": "2026-01-24",
            "frequences_compatibles": ["MONTHLY", "YEARLY"],
            "frequences_incompatibles": [
                {
                    "frequence": "DAILY",
                    "decalage_jours": 1,
                    "raison": "Décalage (1j) < Durée tâche (10j)"
                },
                {
                    "frequence": "WEEKLY",
                    "decalage_jours": 7,
                    "raison": "Décalage (7j) < Durée tâche (10j)"
                }
            ]
        }
        ```
        """
        tache = self.get_object()

        try:
            duree_tache = calculer_duree_tache(tache)
            frequences_compatibles_list = obtenir_frequences_compatibles(tache)

            # Mapping fréquence -> décalage
            frequences_mapping = {
                'DAILY': 1,
                'WEEKLY': 7,
                'MONTHLY': 30,
                'YEARLY': 365,
            }

            # Identifier les fréquences incompatibles avec raison
            frequences_incompatibles = []
            for freq, decalage in frequences_mapping.items():
                if freq not in frequences_compatibles_list:
                    frequences_incompatibles.append({
                        'frequence': freq,
                        'decalage_jours': decalage,
                        'raison': f'Décalage ({decalage}j) < Durée tâche ({duree_tache}j)'
                    })

            return Response({
                'duree_tache_jours': duree_tache,
                'date_debut': tache.date_debut_planifiee.strftime('%Y-%m-%d'),
                'date_fin': tache.date_fin_planifiee.strftime('%Y-%m-%d'),
                'frequences_compatibles': frequences_compatibles_list,
                'frequences_incompatibles': frequences_incompatibles,
                'message': (
                    f'Cette tâche dure {duree_tache} jour(s). '
                    f'Fréquences compatibles : {", ".join(frequences_compatibles_list) if frequences_compatibles_list else "Aucune"}'
                )
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {'error': f'Erreur lors du calcul des fréquences: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ==============================================================================
# EXPORT PDF DU PLANNING
# ==============================================================================

import logging
logger = logging.getLogger(__name__)


class PlanningExportPDFView(APIView):
    """
    Export PDF du planning.

    GET /api/planification/export/pdf/

    Params:
        start_date (required): YYYY-MM-DD
        end_date (required): YYYY-MM-DD
        structure_client_id: Filtrer par structure
        equipe_id: Filtrer par equipe
        sync: 'true' pour export synchrone (fallback si Celery non disponible)

    Reponses:
        202: {task_id, status} (mode async)
        200: PDF direct (mode sync)
        400: Erreur de validation des parametres

    Permissions:
        - ADMIN: toutes les taches
        - SUPERVISEUR: taches de ses equipes uniquement
    """
    permission_classes = [permissions.IsAuthenticated, IsAdminOrSuperviseur]

    def get(self, request, *args, **kwargs):
        from celery.result import AsyncResult

        # Valider les parametres obligatoires
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if not start_date or not end_date:
            return Response(
                {'error': 'Les parametres start_date et end_date sont requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Valider le format des dates
        try:
            datetime.strptime(start_date, '%Y-%m-%d')
            datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            return Response(
                {'error': 'Format de date invalide. Utilisez YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Construire les filtres optionnels
        filters = {}
        structure_client_id = request.query_params.get('structure_client_id')
        if structure_client_id:
            try:
                filters['structure_client_id'] = int(structure_client_id)
            except ValueError:
                return Response(
                    {'error': 'structure_client_id doit etre un entier'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        equipe_id = request.query_params.get('equipe_id')
        if equipe_id:
            try:
                filters['equipe_id'] = int(equipe_id)
            except ValueError:
                return Response(
                    {'error': 'equipe_id doit etre un entier'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Mode synchrone (fallback)
        sync_mode = request.query_params.get('sync', 'false').lower() == 'true'

        if sync_mode:
            # Export synchrone direct
            logger.info(f"[PDF Export] Mode SYNC pour user {request.user.id}: {start_date} -> {end_date}")
            from .tasks import export_planning_pdf_async
            result = export_planning_pdf_async(
                user_id=request.user.id,
                start_date=start_date,
                end_date=end_date,
                filters=filters
            )

            if result.get('success'):
                return Response({
                    'task_id': 'sync',
                    'status': 'SUCCESS',
                    'ready': True,
                    'result': {
                        'download_url': result.get('download_url'),
                        'filename': result.get('filename'),
                        'record_count': result.get('record_count', 0),
                    }
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    'error': result.get('error', 'Erreur inconnue')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Mode asynchrone (Celery)
        logger.info(f"[PDF Export] Mode ASYNC pour user {request.user.id}: {start_date} -> {end_date}")

        from .tasks import export_planning_pdf_async
        task = export_planning_pdf_async.delay(
            user_id=request.user.id,
            start_date=start_date,
            end_date=end_date,
            filters=filters
        )

        logger.info(f"[PDF Export] Task Celery cree: {task.id}")

        return Response({
            'task_id': task.id,
            'status': 'PENDING',
            'message': 'Export PDF en cours de generation...'
        }, status=status.HTTP_202_ACCEPTED)


class PlanningExportStatusView(APIView):
    """
    Verifie le statut d'un export PDF.

    GET /api/planification/export/status/<task_id>/

    Reponses:
        200: {status, ready, result} si termine
        200: {status: 'PENDING', ready: false} si en cours
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, task_id, *args, **kwargs):
        from celery.result import AsyncResult

        task_result = AsyncResult(task_id)

        response_data = {
            'task_id': task_id,
            'status': task_result.status,
            'ready': task_result.ready(),
        }

        if task_result.ready():
            if task_result.successful():
                result = task_result.result
                if result.get('success'):
                    response_data['result'] = {
                        'download_url': result.get('download_url'),
                        'filename': result.get('filename'),
                        'record_count': result.get('record_count', 0),
                    }
                else:
                    response_data['error'] = result.get('error', 'Erreur inconnue')
            else:
                response_data['error'] = str(task_result.result) if task_result.result else 'Erreur lors de l\'export'

        return Response(response_data, status=status.HTTP_200_OK)
