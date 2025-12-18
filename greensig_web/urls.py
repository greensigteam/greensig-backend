from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

"""
URL configuration for greensig_web project.
"""

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/users/', include('api_users.urls')),
    path('api/planification/', include('api_planification.urls')),
    path('api/suivi-taches/', include('api_suivi_taches.urls')),
    path('api/reclamations/', include('api_reclamations.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
