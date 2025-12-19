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

class TypeTacheViewSet(viewsets.ModelViewSet):
    queryset = TypeTache.objects.all()
    serializer_class = TypeTacheSerializer
    permission_classes = [permissions.IsAuthenticated]

class TacheViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour les tâches avec permissions automatiques:
    - ADMIN: voit toutes les tâches
    - CLIENT: voit uniquement les tâches de ses sites
    - CHEF_EQUIPE: voit uniquement les tâches assignées à ses équipes
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Q

        # Exclude soft-deleted tasks
        qs = Tache.objects.filter(deleted_at__isnull=True)

        # Optimiser les requêtes avec prefetch_related pour les M2M
        qs = qs.select_related('id_client', 'id_type_tache', 'id_equipe', 'reclamation')
        qs = qs.prefetch_related('equipes', 'objets', 'participations')

        # Appliquer les permissions automatiques basées sur le rôle
        user = self.request.user
        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # ADMIN voit tout
            if 'ADMIN' not in roles:
                # CLIENT voit uniquement les tâches de ses clients
                if 'CLIENT' in roles and hasattr(user, 'client_profile'):
                    qs = qs.filter(id_client=user.client_profile)

                # CHEF_EQUIPE voit uniquement les tâches de ses équipes
                elif 'CHEF_EQUIPE' in roles:
                    try:
                        from api_users.models import Equipe
                        operateur = user.operateur_profile
                        equipes_gerees_ids = list(Equipe.objects.filter(
                            chef_equipe=operateur,
                            actif=True
                        ).values_list('id', flat=True))

                        if equipes_gerees_ids:
                            q_filter = Q(equipes__id__in=equipes_gerees_ids) | Q(id_equipe__in=equipes_gerees_ids)
                            qs = qs.filter(q_filter).distinct()
                        else:
                            # Chef d'équipe sans équipes gérées - retourner aucune tâche
                            qs = qs.none()
                    except Exception:
                        # Si pas d'opérateur profile, retourner aucune tâche
                        qs = qs.none()

        # Filtres optionnels (query params)
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

        return qs

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return TacheCreateUpdateSerializer
        return TacheSerializer

    def perform_destroy(self, instance):
        # Soft delete
        instance.deleted_at = timezone.now()
        instance.save()

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
        """
        # Vérifier que l'utilisateur est ADMIN
        user = request.user
        roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]
        if 'ADMIN' not in roles:
            return Response(
                {'error': 'Seul un administrateur peut valider ou rejeter une tâche'},
                status=status.HTTP_403_FORBIDDEN
            )

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
        tache.validee_par = user
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
    API endpoint pour gérer les ratios de productivité.
    Permet de définir les ratios par combinaison (type de tâche, type d'objet).
    """
    queryset = RatioProductivite.objects.select_related('id_type_tache').all()
    serializer_class = RatioProductiviteSerializer
    permission_classes = [permissions.IsAuthenticated]

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
