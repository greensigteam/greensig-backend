# api/urls.py
from django.urls import path
from .views import (
    # Hiérarchie spatiale
    SiteListCreateView, SiteDetailView,
    SousSiteListCreateView, SousSiteDetailView,
    DetectSiteView,
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
    InventoryExportExcelView,
    InventoryExportPDFView,
    # Inventaire unifié
    InventoryListView,
    InventoryFilterOptionsView,
    # Carte avec bounding box
    MapObjectsView,
    # Import géographique
    GeoImportPreviewView,
    GeoImportValidateView,
    GeoImportExecuteView,
    # Opérations géométriques
    GeometrySimplifyView,
    GeometrySplitView,
    GeometryMergeView,
    GeometryValidateView,
    GeometryCalculateView,
    GeometryBufferView,
)
from .site_statistics_view import SiteStatisticsView
from .reporting_view import ReportingView
from .monthly_report_view import MonthlyReportView
from .kpi_view import KPIView, KPIHistoriqueView
from .views_notifications import (
    NotificationListView,
    UnreadCountView,
    MarkReadView,
    MarkAllReadView,
    NotificationDeleteView,
    SendTestNotificationView,
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
    path('reporting/', ReportingView.as_view(), name='reporting'),
    path('monthly-report/', MonthlyReportView.as_view(), name='monthly-report'),
    path('kpis/', KPIView.as_view(), name='kpis'),
    path('kpis/historique/', KPIHistoriqueView.as_view(), name='kpis-historique'),

    # ==============================================================================
    # EXPORT DONNÉES
    # ==============================================================================
    # Routes spécifiques AVANT la route générique
    path('export/inventory/excel/', InventoryExportExcelView.as_view(), name='inventory-export-excel'),
    path('export/inventory/pdf/', InventoryExportPDFView.as_view(), name='inventory-export-pdf'),
    path('export/<str:model_name>/', ExportDataView.as_view(), name='export-data'),

    # ==============================================================================
    # IMPORT GÉOGRAPHIQUE (GeoJSON, KML, Shapefile)
    # ==============================================================================
    path('import/preview/', GeoImportPreviewView.as_view(), name='import-preview'),
    path('import/validate/', GeoImportValidateView.as_view(), name='import-validate'),
    path('import/execute/', GeoImportExecuteView.as_view(), name='import-execute'),

    # ==============================================================================
    # OPÉRATIONS GÉOMÉTRIQUES
    # ==============================================================================
    path('geometry/simplify/', GeometrySimplifyView.as_view(), name='geometry-simplify'),
    path('geometry/split/', GeometrySplitView.as_view(), name='geometry-split'),
    path('geometry/merge/', GeometryMergeView.as_view(), name='geometry-merge'),
    path('geometry/validate/', GeometryValidateView.as_view(), name='geometry-validate'),
    path('geometry/calculate/', GeometryCalculateView.as_view(), name='geometry-calculate'),
    path('geometry/buffer/', GeometryBufferView.as_view(), name='geometry-buffer'),

    # ==============================================================================
    # INVENTAIRE UNIFIÉ (15 types combinés)
    # ==============================================================================
    path('inventory/', InventoryListView.as_view(), name='inventory-unified'),
    path('inventory/filter-options/', InventoryFilterOptionsView.as_view(), name='inventory-filter-options'),

    # ==============================================================================
    # HIÉRARCHIE SPATIALE
    # ==============================================================================
    path('sites/', SiteListCreateView.as_view(), name='site-list'),
    path('sites/<int:pk>/', SiteDetailView.as_view(), name='site-detail'),
    path('sites/<int:site_id>/statistics/', SiteStatisticsView.as_view(), name='site-statistics'),
    path('sites/detect/', DetectSiteView.as_view(), name='site-detect'),
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

    # ==============================================================================
    # NOTIFICATIONS TEMPS REEL
    # ==============================================================================
    path('notifications/', NotificationListView.as_view(), name='notification-list'),
    path('notifications/unread-count/', UnreadCountView.as_view(), name='notification-unread-count'),
    path('notifications/mark-all-read/', MarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('notifications/test/', SendTestNotificationView.as_view(), name='notification-test'),
    path('notifications/<int:pk>/mark-read/', MarkReadView.as_view(), name='notification-mark-read'),
    path('notifications/<int:pk>/', NotificationDeleteView.as_view(), name='notification-delete'),
]
