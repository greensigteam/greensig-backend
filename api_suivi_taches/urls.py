"""
URLs pour le module Suivi des Tâches
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProduitViewSet,
    ProduitMatiereActiveViewSet,
    DoseProduitViewSet,
    ConsommationProduitViewSet,
    PhotoViewSet,
    FertilisantViewSet,
    RavageurMaladieViewSet
)

router = DefaultRouter()
router.register(r'produits', ProduitViewSet, basename='produit')
router.register(r'matieres-actives', ProduitMatiereActiveViewSet, basename='matiere-active')
router.register(r'doses', DoseProduitViewSet, basename='dose')
router.register(r'consommations', ConsommationProduitViewSet, basename='consommation')
router.register(r'photos', PhotoViewSet, basename='photo')
router.register(r'fertilisants', FertilisantViewSet, basename='fertilisant')
router.register(r'ravageurs-maladies', RavageurMaladieViewSet, basename='ravageur-maladie')

urlpatterns = [
    path('', include(router.urls)),
]
