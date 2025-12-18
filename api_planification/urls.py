from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TacheViewSet, TypeTacheViewSet, RatioProductiviteViewSet

router = DefaultRouter()
router.register(r'taches', TacheViewSet, basename='tache')
router.register(r'types-taches', TypeTacheViewSet, basename='type-tache')
router.register(r'ratios-productivite', RatioProductiviteViewSet, basename='ratio-productivite')

urlpatterns = [
    path('', include(router.urls)),
]
