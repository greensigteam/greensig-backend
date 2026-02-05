from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TacheViewSet, TypeTacheViewSet, RatioProductiviteViewSet, DistributionChargeViewSet,
    PlanningExportPDFView, PlanningExportStatusView
)

router = DefaultRouter()
router.register(r'taches', TacheViewSet, basename='tache')
router.register(r'types-taches', TypeTacheViewSet, basename='type-tache')
router.register(r'ratios-productivite', RatioProductiviteViewSet, basename='ratio-productivite')
router.register(r'distributions', DistributionChargeViewSet, basename='distribution-charge')

urlpatterns = [
    path('', include(router.urls)),
    path('export/pdf/', PlanningExportPDFView.as_view(), name='planning-export-pdf'),
    path('export/status/<str:task_id>/', PlanningExportStatusView.as_view(), name='planning-export-status'),
]
