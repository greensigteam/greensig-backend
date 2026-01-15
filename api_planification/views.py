from django.db import models
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Tache, TypeTache, ParticipationTache, RatioProductivite, DistributionCharge
from .serializers import (
    TacheSerializer, TacheCreateUpdateSerializer,
    TypeTacheSerializer, ParticipationTacheSerializer,
    RatioProductiviteSerializer, DistributionChargeSerializer,
    DupliquerTacheSerializer, DupliquerTacheRecurrenceSerializer,
    DupliquerTacheDatesSpecifiquesSerializer, TacheRecurrenceResponseSerializer
)
from .services import WorkloadCalculationService
from django.utils import timezone
from .utils import (
    dupliquer_tache_avec_distributions,
    dupliquer_tache_recurrence_multiple,
    dupliquer_tache_dates_specifiques,
    obtenir_frequences_compatibles,
    calculer_duree_tache
)
from rest_framework.pagination import PageNumberPagination
from api_users.mixins import RoleBasedQuerySetMixin, RoleBasedPermissionMixin, SoftDeleteMixin
from api_users.permissions import IsAdmin, IsAdminOrReadOnly, IsSuperviseur


# ==============================================================================
# PAGINATION PERSONNALISÉE
# ==============================================================================

class SmallPageNumberPagination(PageNumberPagination):
    """Pagination avec 20 items par page pour les ressources système."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


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

class TacheViewSet(RoleBasedQuerySetMixin, RoleBasedPermissionMixin, SoftDeleteMixin, viewsets.ModelViewSet):
    """
    ViewSet pour les tâches avec permissions automatiques via mixins.

    Permissions (via RoleBasedPermissionMixin):
    - ADMIN: CRUD complet + validation
    - SUPERVISEUR: CRUD sur les tâches de ses équipes (filtrage automatique)
    - CLIENT: Lecture seule sur les tâches de ses sites (filtrage automatique)

    Filtrage automatique: RoleBasedQuerySetMixin filtre selon le rôle
    Soft delete: SoftDeleteMixin gère la suppression douce
    """
    queryset = Tache.objects.all()
    serializer_class = TacheSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    # Permissions par action (RoleBasedPermissionMixin)
    permission_classes_by_action = {
        'create': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
        'update': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
        'partial_update': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
        'destroy': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
        'update_distributions': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
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

        Le soft-delete est géré par SoftDeleteMixin (exclut deleted_at != null).
        """
        from django.db.models import Q, Prefetch
        from api_users.models import Equipe

        # Appeler le mixin pour filtrage par rôle + soft-delete
        qs = super().get_queryset()

        # ⚡ OPTIMISATION: Charger uniquement les relations essentielles pour la liste
        qs = qs.select_related(
            'id_client__utilisateur',
            'id_structure_client',
            'id_type_tache',
            'id_equipe',  # Simplifié: pas de chaîne profonde
            'reclamation'
        )

        # ⚡ PREFETCH MINIMAL: Seulement les infos utilisées par les serializers minimaux
        # ObjetMinimalSerializer: id, site_id, site_nom → besoin de 'objets__site' (only ID + nom)
        # EquipeMinimalSerializer: id, nom_equipe → aucun prefetch nécessaire
        qs = qs.prefetch_related(
            'equipes',  # Juste les IDs et noms (pas de relations supplémentaires)
            'objets__site',  # Site ID + nom seulement (via ObjetMinimalSerializer)
            'distributions_charge'  # ✅ Evite N+1 pour les distributions
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
        return TacheSerializer

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

    # perform_destroy() est géré par SoftDeleteMixin

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

        Permission: IsAdmin ou IsSuperviseur
        """
        tache = self.get_object()
        distributions_data = request.data.get('distributions', [])

        if not isinstance(distributions_data, list):
            return Response(
                {'error': 'Le champ "distributions" doit être une liste'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Supprimer les anciennes distributions
        tache.distributions_charge.all().delete()

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

        # Retourner la tâche mise à jour
        serializer = self.get_serializer(tache)
        return Response({
            'message': f'Tâche {etat.lower()} avec succès',
            'tache': serializer.data
        })

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

class DistributionChargeViewSet(viewsets.ModelViewSet):
    """
    ✅ API endpoint pour gérer les distributions de charge journalières.

    Permet de définir précisément la charge planifiée par jour pour des tâches
    s'étendant sur plusieurs jours.

    Permissions:
    - ADMIN: CRUD complet
    - SUPERVISEUR: CRUD pour les tâches de ses équipes
    - CLIENT: Lecture seule

    Filtres disponibles:
    - ?tache={id} : Distributions pour une tâche spécifique
    - ?date={YYYY-MM-DD} : Distributions pour une date spécifique
    - ?date_debut={YYYY-MM-DD}&date_fin={YYYY-MM-DD} : Distributions dans une période

    Exemples:
    - GET /api/planification/distributions/?tache=123
    - GET /api/planification/distributions/?date=2024-01-15
    - GET /api/planification/distributions/?date_debut=2024-01-15&date_fin=2024-01-20
    """
    queryset = DistributionCharge.objects.select_related('tache').all()
    serializer_class = DistributionChargeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()

        # Filtrer par tâche
        tache_id = self.request.query_params.get('tache')
        if tache_id:
            qs = qs.filter(tache_id=tache_id)

        # Filtrer par date exacte
        date = self.request.query_params.get('date')
        if date:
            qs = qs.filter(date=date)

        # Filtrer par période
        date_debut = self.request.query_params.get('date_debut')
        date_fin = self.request.query_params.get('date_fin')
        if date_debut:
            qs = qs.filter(date__gte=date_debut)
        if date_fin:
            qs = qs.filter(date__lte=date_fin)

        return qs.order_by('date')

    def get_permissions(self):
        """
        Permissions adaptées par action:
        - ADMIN: Tout
        - SUPERVISEUR: CRUD pour ses équipes
        - CLIENT: Lecture seule
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'marquer_realisee', 'marquer_non_realisee']:
            # Écriture: ADMIN ou SUPERVISEUR
            permission_classes = [permissions.IsAuthenticated, IsAdmin | IsSuperviseur]
        else:
            # Lecture: Tous authentifiés
            permission_classes = [permissions.IsAuthenticated]

        return [permission() for permission in permission_classes]

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
        - Si c'est la première distribution marquée comme réalisée
        - Et que la tâche est en statut PLANIFIEE
        - Alors la tâche passe automatiquement en statut EN_COURS
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
        # passer la tâche en EN_COURS
        if est_premiere_distribution and tache.statut == 'PLANIFIEE':
            tache.statut = 'EN_COURS'
            tache.save()

        serializer = self.get_serializer(distribution)
        return Response({
            'message': 'Distribution marquée comme réalisée',
            'distribution': serializer.data,
            'tache_statut_modifie': est_premiere_distribution and tache.statut == 'EN_COURS'
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='marquer-non-realisee')
    def marquer_non_realisee(self, request, pk=None):
        """
        Marque une distribution comme non réalisée (la remet en statut NON_REALISEE).
        POST /api/planification/distributions/{id}/marquer-non-realisee/

        Logique automatique:
        - Si c'était la dernière distribution réalisée
        - Et que la tâche est en statut EN_COURS
        - Alors la tâche repasse automatiquement en statut PLANIFIEE
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
        if est_derniere_distribution and tache.statut == 'EN_COURS':
            tache.statut = 'PLANIFIEE'
            tache.save()

        serializer = self.get_serializer(distribution)
        return Response({
            'message': 'Distribution marquée comme non réalisée',
            'distribution': serializer.data,
            'tache_statut_modifie': est_derniere_distribution and tache.statut == 'PLANIFIEE'
        }, status=status.HTTP_200_OK)


class TacheViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les tâches avec fonctionnalité de récurrence/duplication.
    """
    queryset = Tache.objects.filter(deleted_at__isnull=True)
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
