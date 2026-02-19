# api/views.py
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Count
from django.contrib.gis.geos import GEOSGeometry
from celery.result import AsyncResult
import json

from api_users.permissions import IsAdmin, IsAdminOrSuperviseur, CanExportData

from .models import (
    Site, SousSite, Objet, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)
from .serializers import (
    SiteSerializer, SousSiteSerializer, ArbreSerializer, GazonSerializer,
    PalmierSerializer, ArbusteSerializer, VivaceSerializer, CactusSerializer,
    GramineeSerializer, PuitSerializer, PompeSerializer, VanneSerializer,
    ClapetSerializer, CanalisationSerializer, AspersionSerializer,
    GoutteSerializer, BallonSerializer
)
from .filters import (
    SiteFilter, SousSiteFilter, ArbreFilter, GazonFilter, PalmierFilter,
    ArbusteFilter, VivaceFilter, CactusFilter, GramineeFilter, PuitFilter,
    PompeFilter, VanneFilter, ClapetFilter, CanalisationFilter,
    AspersionFilter, GoutteFilter, BallonFilter
)


# ==============================================================================
# MIXIN POUR LE FILTRAGE DES OBJETS GIS PAR PERMISSIONS
# ==============================================================================

class GISObjectPermissionMixin:
    """
    Mixin pour filtrer automatiquement les objets GIS selon les permissions utilisateur.

    Tous les objets GIS ont un champ 'site' qui permet de filtrer selon:
    - ADMIN: voit tous les objets
    - CLIENT: voit uniquement les objets de ses sites
    - SUPERVISEUR: voit uniquement les objets des sites qui lui sont affectés
    """
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return queryset.none()

        roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

        # ADMIN voit tout
        if 'ADMIN' in roles:
            return queryset

        # CLIENT voit uniquement les objets des sites de sa structure
        if 'CLIENT' in roles and hasattr(user, 'client_profile'):
            structure = user.client_profile.structure
            if structure:
                return queryset.filter(site__structure_client=structure)
            return queryset.none()

        # SUPERVISEUR voit uniquement les objets des sites qui lui sont affectés
        if 'SUPERVISEUR' in roles and hasattr(user, 'superviseur_profile'):
            return queryset.filter(site__superviseur=user.superviseur_profile)

        # Par défaut, aucun accès
        return queryset.none()


# ==============================================================================
# VUE POUR VÉRIFIER LE STATUT DES TÂCHES CELERY
# ==============================================================================

class TaskStatusView(APIView):
    """
    Vue pour vérifier le statut d'une tâche Celery asynchrone.

    GET /api/tasks/<task_id>/status/

    Retourne:
    - status: PENDING, STARTED, SUCCESS, FAILURE, RETRY, REVOKED
    - result: Résultat si SUCCESS, message d'erreur si FAILURE
    - ready: True si la tâche est terminée
    """

    def get(self, request, task_id, *args, **kwargs):
        result = AsyncResult(task_id)

        response_data = {
            'task_id': task_id,
            'status': result.status,
            'ready': result.ready(),
        }

        if result.ready():
            if result.successful():
                response_data['result'] = result.result
            else:
                # Tâche échouée
                response_data['error'] = str(result.result) if result.result else 'Unknown error'

        return Response(response_data)


# ==============================================================================
# VUES POUR LA HIÉRARCHIE SPATIALE
# ==============================================================================

class SiteListCreateView(generics.ListCreateAPIView):
    serializer_class = SiteSerializer
    filterset_class = SiteFilter

    def get_queryset(self):
        """
        Filtrage automatique basé sur les permissions utilisateur:
        - ADMIN: voit tous les sites
        - CLIENT: voit uniquement ses sites
        - SUPERVISEUR: voit uniquement les sites liés aux tâches de ses équipes
        """
        queryset = Site.objects.all().order_by('id')
        user = self.request.user

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # ADMIN voit tout
            if 'ADMIN' in roles:
                return queryset

            # CLIENT voit uniquement les sites de sa structure
            if 'CLIENT' in roles and hasattr(user, 'client_profile'):
                structure = user.client_profile.structure
                if structure:
                    return queryset.filter(structure_client=structure)
                return queryset.none()

            # SUPERVISEUR voit uniquement les sites qui lui sont affectés directement
            if 'SUPERVISEUR' in roles:
                if hasattr(user, 'superviseur_profile'):
                    return queryset.filter(superviseur=user.superviseur_profile)
                else:
                    # Superviseur sans profil = aucun site visible
                    return queryset.none()

        # Par défaut, aucun accès pour les utilisateurs sans rôle reconnu
        return queryset.none()

    def _get_superviseur_site_ids(self, user):
        """
        Récupère les IDs des sites contenant les objets liés aux tâches du superviseur.
        Seuls les sites avec des objets dans les tâches sont retournés.

        OPTIMISÉ: Une seule requête SQL au lieu de N+1.
        """
        from api_planification.models import Tache

        try:
            superviseur = user.superviseur_profile
            # Équipes gérées par ce superviseur
            equipes_gerees = superviseur.equipes_gerees.filter(actif=True)
            equipes_gerees_ids = list(equipes_gerees.values_list('id', flat=True))

            if not equipes_gerees_ids:
                return []

            # Tâches assignées à ces équipes
            taches_ids = Tache.objects.filter(
                Q(equipes__id__in=equipes_gerees_ids) | Q(id_equipe__in=equipes_gerees_ids)
            ).values_list('id', flat=True).distinct()

            # OPTIMISÉ: Récupérer les site_ids en une seule requête via la relation inverse
            # Au lieu de boucler sur chaque tâche puis chaque objet (N+1)
            site_ids = list(Objet.objects.filter(
                taches__id__in=taches_ids,
                site_id__isnull=False
            ).values_list('site_id', flat=True).distinct())

            return site_ids
        except Exception:
            return []


class SiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SiteSerializer

    def get_queryset(self):
        """
        Filtrage automatique basé sur les permissions utilisateur:
        - ADMIN: voit tous les sites
        - CLIENT: voit uniquement ses sites
        - SUPERVISEUR: voit uniquement les sites qui lui sont affectés
        """
        queryset = Site.objects.all()
        user = self.request.user

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # ADMIN voit tout
            if 'ADMIN' in roles:
                return queryset

            # CLIENT voit uniquement les sites de sa structure
            if 'CLIENT' in roles and hasattr(user, 'client_profile'):
                structure = user.client_profile.structure
                if structure:
                    return queryset.filter(structure_client=structure)
                return queryset.none()

            # SUPERVISEUR voit uniquement les sites qui lui sont affectés
            if 'SUPERVISEUR' in roles:
                if hasattr(user, 'superviseur_profile'):
                    return queryset.filter(superviseur=user.superviseur_profile)
                else:
                    return queryset.none()

        return queryset.none()


class SousSiteListCreateView(generics.ListCreateAPIView):
    queryset = SousSite.objects.all().order_by('id')
    serializer_class = SousSiteSerializer
    filterset_class = SousSiteFilter

    def get_queryset(self):
        """
        Filtrage automatique basé sur les permissions utilisateur:
        - ADMIN: voit tous les sous-sites
        - CLIENT: voit uniquement les sous-sites de ses sites
        - SUPERVISEUR: voit uniquement les sous-sites des sites qui lui sont affectés
        """
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # ADMIN voit tout
            if 'ADMIN' in roles:
                return queryset

            # CLIENT voit uniquement les sous-sites des sites de sa structure
            if 'CLIENT' in roles and hasattr(user, 'client_profile'):
                structure = user.client_profile.structure
                if structure:
                    return queryset.filter(site__structure_client=structure)
                return queryset.none()

            # SUPERVISEUR voit uniquement les sous-sites des sites qui lui sont affectés
            if 'SUPERVISEUR' in roles:
                if hasattr(user, 'superviseur_profile'):
                    return queryset.filter(site__superviseur=user.superviseur_profile)
                else:
                    return queryset.none()

        return queryset.none()


class SousSiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SousSite.objects.all()
    serializer_class = SousSiteSerializer

    def get_queryset(self):
        """
        Filtrage automatique basé sur les permissions utilisateur:
        - ADMIN: voit tous les sous-sites
        - CLIENT: voit uniquement les sous-sites de ses sites
        - SUPERVISEUR: voit uniquement les sous-sites des sites qui lui sont affectés
        """
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # ADMIN voit tout
            if 'ADMIN' in roles:
                return queryset

            # CLIENT voit uniquement les sous-sites des sites de sa structure
            if 'CLIENT' in roles and hasattr(user, 'client_profile'):
                structure = user.client_profile.structure
                if structure:
                    return queryset.filter(site__structure_client=structure)
                return queryset.none()

            # SUPERVISEUR voit uniquement les sous-sites des sites qui lui sont affectés
            if 'SUPERVISEUR' in roles and hasattr(user, 'superviseur_profile'):
                return queryset.filter(site__superviseur=user.superviseur_profile)

        return queryset


class DetectSiteView(APIView):
    """
    Détecte le site contenant une géométrie donnée.

    POST /api/sites/detect/
    Body: { "geometry": { "type": "Point|Polygon|LineString", "coordinates": [...] } }

    Returns:
        - 200: { "site": { id, nom_site, code_site }, "sous_site": { id, nom } | null }
        - 404: { "error": "Aucun site ne contient cette géométrie" }
        - 400: { "error": "Géométrie invalide" }
    """

    def post(self, request):
        geometry_data = request.data.get('geometry')

        if not geometry_data:
            return Response(
                {'error': 'Le champ "geometry" est requis'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Convert GeoJSON to GEOS geometry
            geom = GEOSGeometry(json.dumps(geometry_data), srid=4326)
        except Exception as e:
            return Response(
                {'error': f'Géométrie invalide: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # For points, use intersects; for polygons/lines, check if contained or intersects
        # We use intersects to be more flexible (an object can touch the boundary)
        site = Site.objects.filter(geometrie_emprise__intersects=geom).first()

        if not site:
            return Response(
                {'error': 'Aucun site ne contient cette géométrie. Veuillez dessiner à l\'intérieur d\'un site existant.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Also try to detect sous-site (for points especially)
        sous_site = None
        if geom.geom_type == 'Point':
            # For points, find the nearest sous-site within a small tolerance
            sous_site_obj = SousSite.objects.filter(
                site=site,
                geometrie__distance_lte=(geom, 0.001)  # ~100m tolerance
            ).first()
            if sous_site_obj:
                sous_site = {
                    'id': sous_site_obj.id,
                    'nom': sous_site_obj.nom
                }

        return Response({
            'site': {
                'id': site.id,
                'nom_site': site.nom_site,
                'code_site': site.code_site
            },
            'sous_site': sous_site
        })


# ==============================================================================
# VUES POUR LES VÉGÉTAUX
# ==============================================================================

class ArbreListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Arbre.objects.all().order_by('id')
    serializer_class = ArbreSerializer
    filterset_class = ArbreFilter


class ArbreDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Arbre.objects.all()
    serializer_class = ArbreSerializer


class GazonListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Gazon.objects.all().order_by('id')
    serializer_class = GazonSerializer
    filterset_class = GazonFilter


class GazonDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Gazon.objects.all()
    serializer_class = GazonSerializer


class PalmierListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Palmier.objects.all().order_by('id')
    serializer_class = PalmierSerializer
    filterset_class = PalmierFilter


class PalmierDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Palmier.objects.all()
    serializer_class = PalmierSerializer


class ArbusteListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Arbuste.objects.all().order_by('id')
    serializer_class = ArbusteSerializer
    filterset_class = ArbusteFilter


class ArbusteDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Arbuste.objects.all()
    serializer_class = ArbusteSerializer


class VivaceListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Vivace.objects.all().order_by('id')
    serializer_class = VivaceSerializer
    filterset_class = VivaceFilter


class VivaceDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Vivace.objects.all()
    serializer_class = VivaceSerializer


class CactusListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Cactus.objects.all().order_by('id')
    serializer_class = CactusSerializer
    filterset_class = CactusFilter


class CactusDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Cactus.objects.all()
    serializer_class = CactusSerializer


class GramineeListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Graminee.objects.all().order_by('id')
    serializer_class = GramineeSerializer
    filterset_class = GramineeFilter


class GramineeDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Graminee.objects.all()
    serializer_class = GramineeSerializer


# ==============================================================================
# VUES POUR L'HYDRAULIQUE
# ==============================================================================

class PuitListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Puit.objects.all().order_by('id')
    serializer_class = PuitSerializer
    filterset_class = PuitFilter


class PuitDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Puit.objects.all()
    serializer_class = PuitSerializer


class PompeListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Pompe.objects.all().order_by('id')
    serializer_class = PompeSerializer
    filterset_class = PompeFilter


class PompeDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Pompe.objects.all()
    serializer_class = PompeSerializer


class VanneListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Vanne.objects.all().order_by('id')
    serializer_class = VanneSerializer
    filterset_class = VanneFilter


class VanneDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Vanne.objects.all()
    serializer_class = VanneSerializer


class ClapetListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Clapet.objects.all().order_by('id')
    serializer_class = ClapetSerializer
    filterset_class = ClapetFilter


class ClapetDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Clapet.objects.all()
    serializer_class = ClapetSerializer


class CanalisationListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Canalisation.objects.all().order_by('id')
    serializer_class = CanalisationSerializer
    filterset_class = CanalisationFilter


class CanalisationDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Canalisation.objects.all()
    serializer_class = CanalisationSerializer


class AspersionListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Aspersion.objects.all().order_by('id')
    serializer_class = AspersionSerializer
    filterset_class = AspersionFilter


class AspersionDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Aspersion.objects.all()
    serializer_class = AspersionSerializer


class GoutteListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Goutte.objects.all().order_by('id')
    serializer_class = GoutteSerializer
    filterset_class = GoutteFilter


class GoutteDetailView(GISObjectPermissionMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Goutte.objects.all()
    serializer_class = GoutteSerializer


class BallonListCreateView(GISObjectPermissionMixin, generics.ListCreateAPIView):
    queryset = Ballon.objects.all().order_by('id')
    serializer_class = BallonSerializer
    filterset_class = BallonFilter


class TankDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Ballon.objects.all()
    serializer_class = BallonSerializer

# ==============================================================================
# VUE POUR LA RECHERCHE
# ==============================================================================

class SearchView(APIView):
    """
    Vue pour la recherche multicritère sur TOUS les types d'objets.
    Accepte un paramètre de requête `q`.
    Recherche dans Sites, SousSites, et tous les 15 types d'objets (végétation + hydraulique).

    🔒 FILTRAGE PAR RÔLE:
    - ADMIN: voit tout
    - CLIENT: voit uniquement ses sites/objets
    - SUPERVISEUR: voit uniquement les sites liés à ses équipes
    """
    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()

        if len(query) < 2:
            return Response([])

        results = []

        # 🔒 Filtrage par rôle utilisateur
        user = request.user
        structure_filter = None
        site_ids_filter = None

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # CLIENT: uniquement les sites de sa structure
            if 'CLIENT' in roles and hasattr(user, 'client_profile'):
                structure_filter = user.client_profile.structure

            # SUPERVISEUR: uniquement les sites de ses équipes
            elif 'SUPERVISEUR' in roles and not ('ADMIN' in roles):
                site_ids_filter = self._get_superviseur_site_ids(user)

        # Recherche sur les Sites (par nom ou code)
        site_query = Q(nom_site__icontains=query) | Q(code_site__icontains=query)
        sites_queryset = Site.objects.filter(site_query)

        # Appliquer le filtrage par rôle
        if structure_filter:
            sites_queryset = sites_queryset.filter(structure_client=structure_filter)
        elif site_ids_filter is not None:
            sites_queryset = sites_queryset.filter(id__in=site_ids_filter)

        sites = sites_queryset.distinct()[:10]  # ✅ Limit to 10 unique sites
        for item in sites:
            location = item.centroid
            results.append({
                'id': f"site-{item.pk}",
                'name': f"{item.nom_site}",
                'type': 'Site',
                'location': {'type': 'Point', 'coordinates': [location.x, location.y]} if location else None,
            })

        # Recherche sur les Sous-Sites (par nom)
        sous_sites_queryset = SousSite.objects.filter(nom__icontains=query)

        # Appliquer le filtrage par rôle
        if structure_filter:
            sous_sites_queryset = sous_sites_queryset.filter(site__structure_client=structure_filter)
        elif site_ids_filter is not None:
            sous_sites_queryset = sous_sites_queryset.filter(site_id__in=site_ids_filter)

        sous_sites = sous_sites_queryset.distinct()[:5]  # ✅ Limit to 5 unique sous-sites
        for item in sous_sites:
            location = item.geometrie
            results.append({
                'id': f"soussite-{item.pk}",
                'name': f"{item.nom} ({item.site.nom_site})",
                'type': 'Sous-site',
                'location': {'type': 'Point', 'coordinates': [location.x, location.y]} if location else None,
            })

        # ✅ Recherche sur TOUS les types d'objets (végétation + hydraulique)
        # Mapping: (Model, type_name, id_prefix)
        object_models = [
            # Végétation (7 types)
            (Arbre, 'Arbre', 'arbre'),
            (Gazon, 'Gazon', 'gazon'),
            (Palmier, 'Palmier', 'palmier'),
            (Arbuste, 'Arbuste', 'arbuste'),
            (Vivace, 'Vivace', 'vivace'),
            (Cactus, 'Cactus', 'cactus'),
            (Graminee, 'Graminée', 'graminee'),
            # Hydraulique (8 types)
            (Puit, 'Puit', 'puit'),
            (Pompe, 'Pompe', 'pompe'),
            (Vanne, 'Vanne', 'vanne'),
            (Clapet, 'Clapet', 'clapet'),
            (Canalisation, 'Canalisation', 'canalisation'),
            (Aspersion, 'Aspersion', 'aspersion'),
            (Goutte, 'Goutte', 'goutte'),
            (Ballon, 'Ballon', 'ballon'),
        ]

        for Model, type_name, id_prefix in object_models:
            try:
                # Recherche par nom (ou marque pour certains types hydrauliques)
                query_filter = Q(nom__icontains=query)
                if hasattr(Model, 'marque'):
                    query_filter |= Q(marque__icontains=query)
                if hasattr(Model, 'famille'):
                    query_filter |= Q(famille__icontains=query)

                objects_queryset = Model.objects.filter(query_filter).select_related('site')

                # 🔒 Appliquer le filtrage par rôle
                if structure_filter:
                    objects_queryset = objects_queryset.filter(site__structure_client=structure_filter)
                elif site_ids_filter is not None:
                    objects_queryset = objects_queryset.filter(site_id__in=site_ids_filter)

                objects = objects_queryset[:5]  # Max 5 par type
                for obj in objects:
                    try:
                        location = obj.geometry if hasattr(obj, 'geometry') else None
                        site_name = obj.site.nom_site if hasattr(obj, 'site') and obj.site else 'Inconnu'

                        # Centroid pour polygones/lignes
                        if location and location.geom_type in ['Polygon', 'LineString', 'MultiPolygon', 'MultiLineString']:
                            location = location.centroid

                        # Nom de l'objet
                        obj_name = obj.nom if hasattr(obj, 'nom') and obj.nom else f"{type_name} #{obj.pk}"

                        results.append({
                            'id': f"{id_prefix}-{obj.pk}",
                            'name': f"{obj_name} ({site_name})",
                            'type': type_name,
                            'location': {'type': 'Point', 'coordinates': [location.x, location.y]} if location else None,
                        })
                    except Exception as e:
                        # Log error but continue with next object
                        print(f"Error processing {type_name} #{obj.pk}: {str(e)}")
                        continue

            except Exception as e:
                # Log error but continue with next model type
                print(f"Error searching {type_name}: {str(e)}")
                continue

        # Limiter le nombre total de résultats
        return Response(results[:30])

    def _get_superviseur_site_ids(self, user):
        """
        Récupère les IDs des sites contenant les objets liés aux tâches du superviseur.
        """
        from api_planification.models import Tache

        try:
            superviseur = user.superviseur_profile
            equipes_gerees = superviseur.equipes_gerees.filter(actif=True)
            equipes_gerees_ids = list(equipes_gerees.values_list('id', flat=True))

            if not equipes_gerees_ids:
                return []

            taches_ids = Tache.objects.filter(
                Q(equipes__id__in=equipes_gerees_ids) | Q(id_equipe__in=equipes_gerees_ids)
            ).values_list('id', flat=True).distinct()

            site_ids = list(Objet.objects.filter(
                taches__id__in=taches_ids,
                site_id__isnull=False
            ).values_list('site_id', flat=True).distinct())

            return site_ids
        except Exception:
            return []
