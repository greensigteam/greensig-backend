from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .models import TypeReclamation, Urgence, Reclamation, HistoriqueReclamation, SatisfactionClient
from api_users.models import Equipe
from django.db import transaction
from .serializers import (
    TypeReclamationSerializer, 
    UrgenceSerializer, 
    ReclamationListSerializer, 
    ReclamationDetailSerializer,
    ReclamationCreateSerializer,
    HistoriqueReclamationSerializer,
    SatisfactionClientSerializer
)

class TypeReclamationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les types de réclamation.
    Lecture seule. Retourne uniquement les actifs.
    """
    queryset = TypeReclamation.objects.filter(actif=True)
    serializer_class = TypeReclamationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ['nom_reclamation', 'categorie']


class UrgenceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les niveaux d'urgence.
    Lecture seule. Ordonné par priorité.
    """
    queryset = Urgence.objects.all().order_by('ordre')
    serializer_class = UrgenceSerializer
    permission_classes = [permissions.IsAuthenticated]


class ReclamationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des réclamations.

    Permissions:
    - Admin/Staff : accès à TOUTES les réclamations
    - Chef d'équipe : accès uniquement à SES réclamations créées
    - Client : accès uniquement à SES réclamations (créées par lui ou liées à lui)
    - Tout utilisateur authentifié peut créer une réclamation
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['statut', 'site', 'zone', 'urgence', 'type_reclamation', 'createur']
    ordering_fields = ['date_creation', 'date_cloture_prevue']
    search_fields = ['numero_reclamation', 'description']

    def get_queryset(self):
        user = self.request.user
        # Optimisation: select_related pour éviter N+1 queries
        queryset = Reclamation.objects.filter(actif=True).select_related(
            'createur',
            'client__utilisateur',
            'site',
            'zone',
            'urgence',
            'type_reclamation',
            'equipe_affectee',
            'equipe_affectee__chef_equipe__utilisateur'
        )

        # Admin / Staff : accès à TOUTES les réclamations
        if user.is_staff or user.is_superuser:
            return queryset

        # Chef d'équipe ou Opérateur : accès uniquement à ses propres réclamations
        if hasattr(user, 'operateur_profile'):
            return queryset.filter(createur=user)

        # Client : accès à ses réclamations uniquement (créées par lui ou liées à lui)
        if hasattr(user, 'client_profile'):
            return queryset.filter(Q(client=user.client_profile) | Q(createur=user))

        # Tout autre utilisateur : réclamations qu'il a créées
        return queryset.filter(createur=user)

    def perform_destroy(self, instance):
        """Soft delete instead of physical deletion."""
        instance.actif = False
        instance.save()

    def get_serializer_class(self):
        if self.action == 'list':
            return ReclamationListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ReclamationCreateSerializer
        return ReclamationDetailSerializer

    def perform_create(self, serializer):
        """
        Assigner automatiquement le créateur (utilisateur connecté).
        Si c'est un client, on associe aussi le client_profile.
        """
        user = self.request.user
        extra_kwargs = {'createur': user}

        # Si l'utilisateur est un client, on associe également le client_profile
        if hasattr(user, 'client_profile'):
            extra_kwargs['client'] = user.client_profile

        reclamation = serializer.save(**extra_kwargs)

        # Création de l'historique initial
        HistoriqueReclamation.objects.create(
            reclamation=reclamation,
            statut_precedent=None,
            statut_nouveau=reclamation.statut,
            auteur=user if user.is_authenticated else None,
            commentaire="Création de la réclamation"
        )

    def perform_update(self, serializer):
        # Récupération de l'instance avant modification pour comparer le statut
        instance = self.get_object()
        old_statut = instance.statut
        
        # Mise à jour automatique des dates selon le statut
        new_statut = serializer.validated_data.get('statut')
        if new_statut and new_statut != old_statut:
            if new_statut == 'PRISE_EN_COMPTE' and not instance.date_prise_en_compte:
                serializer.validated_data['date_prise_en_compte'] = timezone.now()
            elif new_statut == 'EN_COURS' and not instance.date_debut_traitement:
                serializer.validated_data['date_debut_traitement'] = timezone.now()
            elif new_statut == 'RESOLUE' and not instance.date_resolution:
                serializer.validated_data['date_resolution'] = timezone.now()
            elif new_statut == 'CLOTUREE' and not instance.date_cloture_reelle:
                serializer.validated_data['date_cloture_reelle'] = timezone.now()

        updated_instance = serializer.save()
        
        # Si le statut a changé, on ajoute une entrée dans l'historique
        if old_statut != updated_instance.statut:
            HistoriqueReclamation.objects.create(
                reclamation=updated_instance,
                statut_precedent=old_statut,
                statut_nouveau=updated_instance.statut,
                auteur=self.request.user if self.request.user.is_authenticated else None,
                commentaire=f"Changement de statut : {old_statut} -> {updated_instance.statut}"
            )


    @action(detail=True, methods=['get'])
    def suivi(self, request, pk=None):
        """
        Endpoint spécifique pour le suivi temps réel.
        Retourne la timeline et le statut (à enrichir selon besoin).
        """
        reclamation = self.get_object()
        serializer = ReclamationDetailSerializer(reclamation)
        return Response(serializer.data)

    @action(detail=True, methods=['put'])
    def assignation(self, request, pk=None):
        """
        Endpoint pour assigner une réclamation à une équipe.
        Met à jour la réclamation, les tâches associées, et l'historique.
        """
        reclamation = self.get_object()
        equipe_id = request.data.get('equipe_id')
        
        if not equipe_id:
             return Response({"error": "L'ID de l'équipe est requis."}, status=status.HTTP_400_BAD_REQUEST)
             
        try:
             equipe = Equipe.objects.get(pk=equipe_id)
        except Equipe.DoesNotExist:
             return Response({"error": "Équipe non trouvée."}, status=status.HTTP_404_NOT_FOUND)
             
        # Transaction atomique pour garantir la cohérence
        with transaction.atomic():
             old_statut = reclamation.statut
             old_equipe = reclamation.equipe_affectee
             
             # 1. Mise à jour de la Réclamation
             reclamation.equipe_affectee = equipe
             # Si nouvelle -> Prise en compte
             if reclamation.statut == 'NOUVELLE':
                 reclamation.statut = 'PRISE_EN_COMPTE'
                 if not reclamation.date_prise_en_compte:
                     reclamation.date_prise_en_compte = timezone.now()
             reclamation.save()
             
             # 2. Propagation aux Tâches (via le related_name 'taches_correctives')
             # On met à jour toutes les tâches correctives liées
             updated_count = reclamation.taches_correctives.update(id_equipe=equipe)
             
             # 3. Création de l'historique
             commentaire = f"Assignation à l'équipe: {equipe.nom_equipe}"
             if old_equipe:
                 commentaire += f" (anciennement: {old_equipe.nom_equipe})"
             
             if old_statut != reclamation.statut:
                 commentaire += f" - Statut changé de {old_statut} à {reclamation.statut}"

             HistoriqueReclamation.objects.create(
                reclamation=reclamation,
                statut_precedent=old_statut,
                statut_nouveau=reclamation.statut,
                auteur=request.user if request.user.is_authenticated else None,
                commentaire=commentaire
            )
            
        serializer = ReclamationDetailSerializer(reclamation)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """
        Endpoint pour clôturer une réclamation (User 6.6.12).
        Conditions: statut = RESOLUE
        """
        reclamation = self.get_object()
        
        # T6.6.12.1 - Vérification des conditions
        if reclamation.statut != 'RESOLUE':
            return Response(
                {"error": "La réclamation doit être au statut 'Résolue' pour être clôturée."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            old_statut = reclamation.statut
            reclamation.statut = 'CLOTUREE'
            reclamation.date_cloture_reelle = timezone.now()
            reclamation.save()
            
            # Historique
            HistoriqueReclamation.objects.create(
                reclamation=reclamation,
                statut_precedent=old_statut,
                statut_nouveau='CLOTUREE',
                auteur=request.user,
                commentaire="Clôture de la réclamation"
            )
        
        serializer = ReclamationDetailSerializer(reclamation)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Endpoint pour les statistiques des réclamations (User 6.6.14).
        Filtres: date_debut, date_fin, site, zone, type_reclamation
        """
        queryset = self.get_queryset()
        
        # Filtres temporels
        date_debut = request.query_params.get('date_debut')
        date_fin = request.query_params.get('date_fin')
        if date_debut:
            queryset = queryset.filter(date_creation__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(date_creation__lte=date_fin)
        
        # Filtres géographiques
        site_id = request.query_params.get('site')
        zone_id = request.query_params.get('zone')
        if site_id:
            queryset = queryset.filter(site_id=site_id)
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        
        # Filtre type
        type_id = request.query_params.get('type_reclamation')
        if type_id:
            queryset = queryset.filter(type_reclamation_id=type_id)
        
        # Calcul des KPIs
        stats_data = {
            'total': queryset.count(),
            'par_statut': dict(queryset.values('statut').annotate(count=Count('id')).values_list('statut', 'count')),
            'par_type': list(queryset.values('type_reclamation__nom_reclamation').annotate(count=Count('id'))),
            'par_urgence': list(queryset.values('urgence__niveau_urgence').annotate(count=Count('id'))),
            'par_zone': list(queryset.filter(zone__isnull=False).values('zone__nom').annotate(count=Count('id'))),
        }
        
        # Délai moyen de traitement (pour les clôturées)
        cloturees = queryset.filter(statut='CLOTUREE', date_cloture_reelle__isnull=False)
        if cloturees.exists():
            delais = []
            for rec in cloturees:
                if rec.date_creation and rec.date_cloture_reelle:
                    delta = rec.date_cloture_reelle - rec.date_creation
                    delais.append(delta.total_seconds() / 3600)  # en heures
            if delais:
                stats_data['delai_moyen_heures'] = sum(delais) / len(delais)
        
        # Taux de satisfaction
        satisfactions = SatisfactionClient.objects.filter(reclamation__in=queryset)
        if satisfactions.exists():
            stats_data['satisfaction_moyenne'] = satisfactions.aggregate(Avg('note'))['note__avg']
            stats_data['nombre_evaluations'] = satisfactions.count()
        
        return Response(stats_data)


# ==============================================================================
# VIEWSET - SATISFACTION CLIENT (User 6.6.13)
# ==============================================================================

class SatisfactionClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des évaluations de satisfaction client.
    """
    queryset = SatisfactionClient.objects.all()
    serializer_class = SatisfactionClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = SatisfactionClient.objects.all()
        
        # Filtrer par réclamation si spécifié
        reclamation_id = self.request.query_params.get('reclamation')
        if reclamation_id:
            queryset = queryset.filter(reclamation_id=reclamation_id)
        
        return queryset
