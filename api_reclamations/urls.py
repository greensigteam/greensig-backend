from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TypeReclamationViewSet, UrgenceViewSet, ReclamationViewSet, SatisfactionClientViewSet

router = DefaultRouter()
router.register(r'types-reclamations', TypeReclamationViewSet, basename='typereclamation')
router.register(r'urgences', UrgenceViewSet, basename='urgence')
router.register(r'reclamations', ReclamationViewSet, basename='reclamation')
router.register(r'satisfactions', SatisfactionClientViewSet, basename='satisfaction')

urlpatterns = [
    path('', include(router.urls)),
]
