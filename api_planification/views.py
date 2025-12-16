from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Tache, TypeTache, ParticipationTache
from .serializers import (
    TacheSerializer, TacheCreateUpdateSerializer, 
    TypeTacheSerializer, ParticipationTacheSerializer
)
from django.utils import timezone

class TypeTacheViewSet(viewsets.ModelViewSet):
    queryset = TypeTache.objects.all()
    serializer_class = TypeTacheSerializer
    permission_classes = [permissions.IsAuthenticated]

class TacheViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Exclude soft-deleted tasks
        qs = Tache.objects.filter(deleted_at__isnull=True)
        
        # Filtres simples (query params)
        client_id = self.request.query_params.get('client_id')
        if client_id:
            qs = qs.filter(id_client=client_id)
            
        equipe_id = self.request.query_params.get('equipe_id')
        if equipe_id:
            qs = qs.filter(id_equipe=equipe_id)
            
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

    def perform_create(self, serializer):
        tache = serializer.save()
        
        # Gestion Récurrence
        if tache.parametres_recurrence:
            from .services import RecurrenceService
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
        # On régénère si il y a des param de récurrence (le service nettoie avant)
        if tache.parametres_recurrence:
            from .services import RecurrenceService
            RecurrenceService.generate_occurrences(tache)
