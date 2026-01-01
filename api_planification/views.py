from django.db import models
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Tache, TypeTache, ParticipationTache, RatioProductivite
from .serializers import (
    TacheSerializer, TacheCreateUpdateSerializer,
    TypeTacheSerializer, ParticipationTacheSerializer,
    RatioProductiviteSerializer
)
from .services import RecurrenceService, WorkloadCalculationService
from django.utils import timezone
from api_users.mixins import RoleBasedQuerySetMixin, RoleBasedPermissionMixin, SoftDeleteMixin
from api_users.permissions import IsAdmin, IsAdminOrReadOnly, IsSuperviseur

class TypeTacheViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les types de tâches (ressource système).

    Permissions:
    - ADMIN: CRUD complet
    - SUPERVISEUR, CLIENT: Lecture seule
    """
    queryset = TypeTache.objects.all()
    serializer_class = TypeTacheSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]

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

    # Permissions par action (RoleBasedPermissionMixin)
    permission_classes_by_action = {
        'create': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
        'update': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
        'partial_update': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
        'destroy': [permissions.IsAuthenticated, IsAdmin | IsSuperviseur],
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

        # Optimisations de requêtes (select_related, prefetch_related)
        qs = qs.select_related(
            'id_client__utilisateur',
            'id_type_tache',
            'id_equipe__chef_equipe',
            'id_equipe__site',
            'reclamation'
        )

        # Prefetch optimisé pour les équipes avec leurs opérateurs
        equipes_qs = Equipe.objects.select_related(
            'chef_equipe',
            'site__superviseur__utilisateur'  # Site → Superviseur → Utilisateur
        ).prefetch_related('operateurs')

        qs = qs.prefetch_related(
            Prefetch('equipes', queryset=equipes_qs),
            'objets__site',
            'objets__sous_site',
            'participations__id_operateur',
            'id_client__utilisateur__roles_utilisateur__role'
        )

        # Filtres optionnels via query params
        client_id = self.request.query_params.get('client_id')
        if client_id:
            qs = qs.filter(id_client=client_id)

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

    # perform_destroy() est géré par SoftDeleteMixin

    @action(detail=True, methods=['post'])
    def add_participation(self, request, pk=None):
        tache = self.get_object()
        # On force l'id_tache dans les données
        data = request.data.copy()
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
        tache.save()

        # Retourner la tâche mise à jour
        serializer = self.get_serializer(tache)
        return Response({
            'message': f'Tâche {etat.lower()} avec succès',
            'tache': serializer.data
        })

    def perform_create(self, serializer):
        tache = serializer.save()

        # Calcul automatique de la charge estimée
        WorkloadCalculationService.recalculate_and_save(tache)

        # Gestion Récurrence
        if tache.parametres_recurrence:
            RecurrenceService.generate_occurrences(tache)

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
        tache = serializer.save()

        # Recalcul automatique de la charge estimée
        WorkloadCalculationService.recalculate_and_save(tache)

        # On régénère si il y a des param de récurrence (le service nettoie avant)
        if tache.parametres_recurrence:
            RecurrenceService.generate_occurrences(tache)


class RatioProductiviteViewSet(viewsets.ModelViewSet):
    """
    API endpoint pour gérer les ratios de productivité (ressource système).
    Permet de définir les ratios par combinaison (type de tâche, type d'objet).

    Permissions:
    - ADMIN: CRUD complet
    - SUPERVISEUR, CLIENT: Lecture seule
    """
    queryset = RatioProductivite.objects.select_related('id_type_tache').all()
    serializer_class = RatioProductiviteSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrReadOnly]

    def get_queryset(self):
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

        return qs
