"""
Views pour le module Suivi des Tâches
"""
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.db.models import Q

from .models import (
    Produit,
    ProduitMatiereActive,
    DoseProduit,
    ConsommationProduit,
    Photo
)
from .serializers import (
    ProduitListSerializer,
    ProduitDetailSerializer,
    ProduitCreateSerializer,
    ProduitMatiereActiveSerializer,
    DoseProduitSerializer,
    ConsommationProduitSerializer,
    ConsommationProduitCreateSerializer,
    PhotoSerializer,
    PhotoCreateSerializer,
    PhotoListSerializer
)


# ==============================================================================
# VIEWSET - PRODUIT
# ==============================================================================

class ProduitViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les produits phytosanitaires.
    
    Endpoints:
    - GET /produits/ : Liste des produits
    - GET /produits/{id}/ : Détail d'un produit
    - POST /produits/ : Créer un produit
    - PUT/PATCH /produits/{id}/ : Modifier un produit
    - DELETE /produits/{id}/ : Supprimer un produit
    - GET /produits/actifs/ : Liste des produits actifs et valides
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['actif', 'cible']
    search_fields = ['nom_produit', 'numero_homologation', 'cible']
    ordering_fields = ['nom_produit', 'date_validite', 'date_creation']
    ordering = ['nom_produit']
    
    def get_queryset(self):
        """Retourne tous les produits."""
        return Produit.objects.all().prefetch_related('matieres_actives', 'doses')
    
    def get_serializer_class(self):
        """Sélectionne le serializer selon l'action."""
        if self.action == 'list':
            return ProduitListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ProduitCreateSerializer
        return ProduitDetailSerializer
    
    @action(detail=False, methods=['get'])
    def actifs(self, request):
        """
        Retourne uniquement les produits actifs et valides.
        
        GET /produits/actifs/
        """
        today = timezone.now().date()
        produits = self.get_queryset().filter(
            actif=True
        ).filter(
            Q(date_validite__gte=today) | Q(date_validite__isnull=True)
        )
        serializer = ProduitListSerializer(produits, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expires_bientot(self, request):
        """
        Retourne les produits qui expirent dans les 30 jours.
        
        GET /produits/expires_bientot/
        """
        today = timezone.now().date()
        date_limite = today + timezone.timedelta(days=30)
        
        produits = self.get_queryset().filter(
            actif=True,
            date_validite__gte=today,
            date_validite__lte=date_limite
        )
        serializer = ProduitListSerializer(produits, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def soft_delete(self, request, pk=None):
        """
        Désactive un produit (soft delete).
        
        POST /produits/{id}/soft_delete/
        """
        produit = self.get_object()
        produit.actif = False
        produit.save()
        serializer = self.get_serializer(produit)
        return Response({
            'message': 'Produit désactivé avec succès',
            'produit': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """
        Réactive un produit désactivé.
        
        POST /produits/{id}/reactivate/
        """
        produit = self.get_object()
        produit.actif = True
        produit.save()
        serializer = self.get_serializer(produit)
        return Response({
            'message': 'Produit réactivé avec succès',
            'produit': serializer.data
        })
    
    def destroy(self, request, *args, **kwargs):
        """
        Override destroy pour empêcher la suppression définitive.
        Utilise soft delete à la place.
        """
        instance = self.get_object()
        instance.actif = False
        instance.save()
        return Response({
            'message': 'Produit désactivé (soft delete). Utilisez /reactivate/ pour le réactiver.'
        }, status=status.HTTP_200_OK)


# ==============================================================================
# VIEWSET - MATIERE ACTIVE
# ==============================================================================

class ProduitMatiereActiveViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les matières actives des produits.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ProduitMatiereActiveSerializer
    
    def get_queryset(self):
        """Filtre par produit si spécifié."""
        queryset = ProduitMatiereActive.objects.all()
        produit_id = self.request.query_params.get('produit', None)
        if produit_id:
            queryset = queryset.filter(produit_id=produit_id)
        return queryset.order_by('produit', 'ordre')


# ==============================================================================
# VIEWSET - DOSE PRODUIT
# ==============================================================================

class DoseProduitViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les doses recommandées des produits.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = DoseProduitSerializer
    
    def get_queryset(self):
        """Filtre par produit si spécifié."""
        queryset = DoseProduit.objects.all()
        produit_id = self.request.query_params.get('produit', None)
        if produit_id:
            queryset = queryset.filter(produit_id=produit_id)
        return queryset


# ==============================================================================
# VIEWSET - CONSOMMATION PRODUIT
# ==============================================================================

class ConsommationProduitViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les consommations de produits par tâche.
    
    Endpoints:
    - GET /consommations/ : Liste des consommations
    - GET /consommations/{id}/ : Détail d'une consommation
    - POST /consommations/ : Enregistrer une consommation
    - PUT/PATCH /consommations/{id}/ : Modifier une consommation
    - DELETE /consommations/{id}/ : Supprimer une consommation
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tache', 'produit']
    ordering_fields = ['date_utilisation']
    ordering = ['-date_utilisation']
    
    def get_queryset(self):
        """Retourne les consommations avec relations."""
        return ConsommationProduit.objects.select_related(
            'tache',
            'produit'
        ).all()
    
    def get_serializer_class(self):
        """Sélectionne le serializer selon l'action."""
        if self.action in ['create', 'update', 'partial_update']:
            return ConsommationProduitCreateSerializer
        return ConsommationProduitSerializer
    
    @action(detail=False, methods=['get'])
    def par_tache(self, request):
        """
        Retourne les consommations pour une tâche spécifique.
        
        GET /consommations/par_tache/?tache_id=X
        """
        tache_id = request.query_params.get('tache_id')
        if not tache_id:
            return Response(
                {'error': 'Le paramètre tache_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        consommations = self.get_queryset().filter(tache_id=tache_id)
        serializer = self.get_serializer(consommations, many=True)
        return Response(serializer.data)


# ==============================================================================
# VIEWSET - PHOTO
# ==============================================================================

class PhotoViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour gérer les photos des interventions.
    
    Endpoints:
    - GET /photos/ : Liste des photos
    - GET /photos/{id}/ : Détail d'une photo
    - POST /photos/ : Ajouter une photo
    - PUT/PATCH /photos/{id}/ : Modifier une photo
    - DELETE /photos/{id}/ : Supprimer une photo
    - GET /photos/par_tache/?tache_id=X : Photos d'une tâche
    - GET /photos/avant/?tache_id=X : Photos avant d'une tâche
    - GET /photos/apres/?tache_id=X : Photos après d'une tâche
    """
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['type_photo', 'tache', 'objet', 'reclamation']
    ordering_fields = ['date_prise']
    ordering = ['-date_prise']
    
    def get_queryset(self):
        """Retourne toutes les photos."""
        return Photo.objects.all()
    
    def get_serializer_class(self):
        """Sélectionne le serializer selon l'action."""
        if self.action == 'list':
            return PhotoListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PhotoCreateSerializer
        return PhotoSerializer
    
    @action(detail=False, methods=['get'])
    def par_tache(self, request):
        """
        Retourne toutes les photos d'une tâche.

        GET /photos/par_tache/?tache_id=X
        """
        tache_id = request.query_params.get('tache_id')
        if not tache_id:
            return Response(
                {'error': 'Le paramètre tache_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        photos = self.get_queryset().filter(tache_id=tache_id)
        serializer = PhotoListSerializer(photos, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def avant(self, request):
        """
        Retourne les photos AVANT d'une tâche.

        GET /photos/avant/?tache_id=X
        """
        tache_id = request.query_params.get('tache_id')
        if not tache_id:
            return Response(
                {'error': 'Le paramètre tache_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        photos = self.get_queryset().filter(
            tache_id=tache_id,
            type_photo='AVANT'
        )
        serializer = PhotoListSerializer(photos, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def apres(self, request):
        """
        Retourne les photos APRÈS d'une tâche.

        GET /photos/apres/?tache_id=X
        """
        tache_id = request.query_params.get('tache_id')
        if not tache_id:
            return Response(
                {'error': 'Le paramètre tache_id est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        photos = self.get_queryset().filter(
            tache_id=tache_id,
            type_photo='APRES'
        )
        serializer = PhotoListSerializer(photos, many=True, context={'request': request})
        return Response(serializer.data)
