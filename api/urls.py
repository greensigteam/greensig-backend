# api/urls.py
from django.urls import path
from .views import (
    # Hiérarchie spatiale
    SiteListCreateView, SiteDetailView,
    SousSiteListCreateView, SousSiteDetailView,
    # Végétaux
    ArbreListCreateView, ArbreDetailView,
    GazonListCreateView, GazonDetailView,
    PalmierListCreateView, PalmierDetailView,
    ArbusteListCreateView, ArbusteDetailView,
    VivaceListCreateView, VivaceDetailView,
    CactusListCreateView, CactusDetailView,
    GramineeListCreateView, GramineeDetailView,
    # Hydraulique
    PuitListCreateView, PuitDetailView,
    PompeListCreateView, PompeDetailView,
    VanneListCreateView, VanneDetailView,
    ClapetListCreateView, ClapetDetailView,
    CanalisationListCreateView, CanalisationDetailView,
    AspersionListCreateView, AspersionDetailView,
    GoutteListCreateView, GoutteDetailView,
    BallonListCreateView, TankDetailView,
    # Recherche
    SearchView,
    # Export PDF
    ExportPDFView,
    # Statistiques
    StatisticsView,
    # Export données
    ExportDataView,
    # Inventaire unifié
    InventoryListView,
    # Options de filtrage
    FilterOptionsView,
    # Carte avec bounding box
    MapObjectsView,
)

urlpatterns = [
    # ==============================================================================
    # CARTE AVEC BOUNDING BOX (endpoint unifié et optimisé)
    # ==============================================================================
    path('map/', MapObjectsView.as_view(), name='map-objects'),

    # ==============================================================================
    # RECHERCHE
    # ==============================================================================
    path('search/', SearchView.as_view(), name='search'),

    # ==============================================================================
    # EXPORT PDF
    # ==============================================================================
    path('export/pdf/', ExportPDFView.as_view(), name='export-pdf'),

    # ==============================================================================
    # STATISTIQUES
    # ==============================================================================
    path('statistics/', StatisticsView.as_view(), name='statistics'),

    # ==============================================================================
    # EXPORT DONNÉES
    # ==============================================================================
    path('export/<str:model_name>/', ExportDataView.as_view(), name='export-data'),

    # ==============================================================================
    # INVENTAIRE UNIFIÉ (15 types combinés)
    # ==============================================================================
    path('inventory/', InventoryListView.as_view(), name='inventory-unified'),
    path('inventory/filter-options/', FilterOptionsView.as_view(), name='filter-options'),

    # ==============================================================================
    # HIÉRARCHIE SPATIALE
    # ==============================================================================
    path('sites/', SiteListCreateView.as_view(), name='site-list'),
    path('sites/<int:pk>/', SiteDetailView.as_view(), name='site-detail'),
    path('sous-sites/', SousSiteListCreateView.as_view(), name='sous-site-list'),
    path('sous-sites/<int:pk>/', SousSiteDetailView.as_view(), name='sous-site-detail'),

    # ==============================================================================
    # VÉGÉTAUX
    # ==============================================================================
    path('arbres/', ArbreListCreateView.as_view(), name='arbre-list'),
    path('arbres/<int:pk>/', ArbreDetailView.as_view(), name='arbre-detail'),
    path('gazons/', GazonListCreateView.as_view(), name='gazon-list'),
    path('gazons/<int:pk>/', GazonDetailView.as_view(), name='gazon-detail'),
    path('palmiers/', PalmierListCreateView.as_view(), name='palmier-list'),
    path('palmiers/<int:pk>/', PalmierDetailView.as_view(), name='palmier-detail'),
    path('arbustes/', ArbusteListCreateView.as_view(), name='arbuste-list'),
    path('arbustes/<int:pk>/', ArbusteDetailView.as_view(), name='arbuste-detail'),
    path('vivaces/', VivaceListCreateView.as_view(), name='vivace-list'),
    path('vivaces/<int:pk>/', VivaceDetailView.as_view(), name='vivace-detail'),
    path('cactus/', CactusListCreateView.as_view(), name='cactus-list'),
    path('cactus/<int:pk>/', CactusDetailView.as_view(), name='cactus-detail'),
    path('graminees/', GramineeListCreateView.as_view(), name='graminee-list'),
    path('graminees/<int:pk>/', GramineeDetailView.as_view(), name='graminee-detail'),

    # ==============================================================================
    # HYDRAULIQUE
    # ==============================================================================
    path('puits/', PuitListCreateView.as_view(), name='puit-list'),
    path('puits/<int:pk>/', PuitDetailView.as_view(), name='puit-detail'),
    path('pompes/', PompeListCreateView.as_view(), name='pompe-list'),
    path('pompes/<int:pk>/', PompeDetailView.as_view(), name='pompe-detail'),
    path('vannes/', VanneListCreateView.as_view(), name='vanne-list'),
    path('vannes/<int:pk>/', VanneDetailView.as_view(), name='vanne-detail'),
    path('clapets/', ClapetListCreateView.as_view(), name='clapet-list'),
    path('clapets/<int:pk>/', ClapetDetailView.as_view(), name='clapet-detail'),
    path('canalisations/', CanalisationListCreateView.as_view(), name='canalisation-list'),
    path('canalisations/<int:pk>/', CanalisationDetailView.as_view(), name='canalisation-detail'),
    path('aspersions/', AspersionListCreateView.as_view(), name='aspersion-list'),
    path('aspersions/<int:pk>/', AspersionDetailView.as_view(), name='aspersion-detail'),
    path('gouttes/', GoutteListCreateView.as_view(), name='goutte-list'),
    path('gouttes/<int:pk>/', GoutteDetailView.as_view(), name='goutte-detail'),
    path('ballons/', BallonListCreateView.as_view(), name='tank-list'),
    path('ballons/<int:pk>/', TankDetailView.as_view(), name='tank-detail'),
]
