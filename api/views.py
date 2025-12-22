# api/views.py
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q
from django.contrib.gis.geos import GEOSGeometry
import json

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
from .site_statistics_view import SiteStatisticsView


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
        - CHEF_EQUIPE: voit uniquement les sites liés aux tâches de ses équipes
        """
        queryset = Site.objects.all().order_by('id')
        user = self.request.user

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # ADMIN voit tout
            if 'ADMIN' in roles:
                return queryset

            # CLIENT voit uniquement ses sites
            if 'CLIENT' in roles and hasattr(user, 'client_profile'):
                return queryset.filter(client=user.client_profile)

            # CHEF_EQUIPE voit uniquement les sites liés à ses tâches
            if 'CHEF_EQUIPE' in roles:
                site_ids = self._get_chef_equipe_site_ids(user)
                if site_ids:
                    return queryset.filter(id__in=site_ids)
                else:
                    return queryset.none()

        return queryset

    def _get_chef_equipe_site_ids(self, user):
        """
        Récupère les IDs des sites contenant les objets liés aux tâches du chef d'équipe.
        Seuls les sites avec des objets dans les tâches sont retournés.

        OPTIMISÉ: Une seule requête SQL au lieu de N+1.
        """
        from api_users.models import Equipe
        from api_planification.models import Tache

        try:
            operateur = user.operateur_profile
            # Équipes gérées par ce chef d'équipe
            equipes_gerees_ids = list(Equipe.objects.filter(
                chef_equipe=operateur,
                actif=True
            ).values_list('id', flat=True))

            if not equipes_gerees_ids:
                return []

            # Tâches assignées à ces équipes (non supprimées)
            taches_ids = Tache.objects.filter(
                deleted_at__isnull=True
            ).filter(
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
        Filter sites by client if the logged-in user is a CLIENT.
        """
        queryset = Site.objects.all()
        user = self.request.user

        if user.is_authenticated:
            has_client_role = user.roles_utilisateur.filter(role__nom_role='CLIENT').exists()
            if has_client_role and hasattr(user, 'client_profile'):
                queryset = queryset.filter(client=user.client_profile)

        return queryset


class SousSiteListCreateView(generics.ListCreateAPIView):
    queryset = SousSite.objects.all().order_by('id')
    serializer_class = SousSiteSerializer
    filterset_class = SousSiteFilter


class SousSiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SousSite.objects.all()
    serializer_class = SousSiteSerializer


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

class ArbreListCreateView(generics.ListCreateAPIView):
    queryset = Arbre.objects.all().order_by('id')
    serializer_class = ArbreSerializer
    filterset_class = ArbreFilter


class ArbreDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Arbre.objects.all()
    serializer_class = ArbreSerializer


class GazonListCreateView(generics.ListCreateAPIView):
    queryset = Gazon.objects.all().order_by('id')
    serializer_class = GazonSerializer
    filterset_class = GazonFilter


class GazonDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Gazon.objects.all()
    serializer_class = GazonSerializer


class PalmierListCreateView(generics.ListCreateAPIView):
    queryset = Palmier.objects.all().order_by('id')
    serializer_class = PalmierSerializer
    filterset_class = PalmierFilter


class PalmierDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Palmier.objects.all()
    serializer_class = PalmierSerializer


class ArbusteListCreateView(generics.ListCreateAPIView):
    queryset = Arbuste.objects.all().order_by('id')
    serializer_class = ArbusteSerializer
    filterset_class = ArbusteFilter


class ArbusteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Arbuste.objects.all()
    serializer_class = ArbusteSerializer


class VivaceListCreateView(generics.ListCreateAPIView):
    queryset = Vivace.objects.all().order_by('id')
    serializer_class = VivaceSerializer
    filterset_class = VivaceFilter


class VivaceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Vivace.objects.all()
    serializer_class = VivaceSerializer


class CactusListCreateView(generics.ListCreateAPIView):
    queryset = Cactus.objects.all().order_by('id')
    serializer_class = CactusSerializer
    filterset_class = CactusFilter


class CactusDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Cactus.objects.all()
    serializer_class = CactusSerializer


class GramineeListCreateView(generics.ListCreateAPIView):
    queryset = Graminee.objects.all().order_by('id')
    serializer_class = GramineeSerializer
    filterset_class = GramineeFilter


class GramineeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Graminee.objects.all()
    serializer_class = GramineeSerializer


# ==============================================================================
# VUES POUR L'HYDRAULIQUE
# ==============================================================================

class PuitListCreateView(generics.ListCreateAPIView):
    queryset = Puit.objects.all().order_by('id')
    serializer_class = PuitSerializer
    filterset_class = PuitFilter


class PuitDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Puit.objects.all()
    serializer_class = PuitSerializer


class PompeListCreateView(generics.ListCreateAPIView):
    queryset = Pompe.objects.all().order_by('id')
    serializer_class = PompeSerializer
    filterset_class = PompeFilter


class PompeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Pompe.objects.all()
    serializer_class = PompeSerializer


class VanneListCreateView(generics.ListCreateAPIView):
    queryset = Vanne.objects.all().order_by('id')
    serializer_class = VanneSerializer
    filterset_class = VanneFilter


class VanneDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Vanne.objects.all()
    serializer_class = VanneSerializer


class ClapetListCreateView(generics.ListCreateAPIView):
    queryset = Clapet.objects.all().order_by('id')
    serializer_class = ClapetSerializer
    filterset_class = ClapetFilter


class ClapetDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Clapet.objects.all()
    serializer_class = ClapetSerializer


class CanalisationListCreateView(generics.ListCreateAPIView):
    queryset = Canalisation.objects.all().order_by('id')
    serializer_class = CanalisationSerializer
    filterset_class = CanalisationFilter


class CanalisationDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Canalisation.objects.all()
    serializer_class = CanalisationSerializer


class AspersionListCreateView(generics.ListCreateAPIView):
    queryset = Aspersion.objects.all().order_by('id')
    serializer_class = AspersionSerializer
    filterset_class = AspersionFilter


class AspersionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Aspersion.objects.all()
    serializer_class = AspersionSerializer


class GoutteListCreateView(generics.ListCreateAPIView):
    queryset = Goutte.objects.all().order_by('id')
    serializer_class = GoutteSerializer
    filterset_class = GoutteFilter


class GoutteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Goutte.objects.all()
    serializer_class = GoutteSerializer


class BallonListCreateView(generics.ListCreateAPIView):
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
    """
    def get(self, request, *args, **kwargs):
        query = request.query_params.get('q', '').strip()

        if len(query) < 2:
            return Response([])

        results = []

        # Recherche sur les Sites (par nom ou code)
        site_query = Q(nom_site__icontains=query) | Q(code_site__icontains=query)
        sites = Site.objects.filter(site_query)
        for item in sites:
            location = item.centroid
            results.append({
                'id': f"site-{item.pk}",
                'name': f"{item.nom_site}",
                'type': 'Site',
                'location': {'type': 'Point', 'coordinates': [location.x, location.y]} if location else None,
            })

        # Recherche sur les Sous-Sites (par nom)
        sous_sites = SousSite.objects.filter(nom__icontains=query)
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

                objects = Model.objects.filter(query_filter).select_related('site')[:5]  # Max 5 par type
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


# ==============================================================================
# VUE POUR L'EXPORT PDF
# ==============================================================================

class ExportPDFView(APIView):
    """
    Vue pour exporter la carte en PDF.
    Accepte les paramètres: title, mapImageBase64, visibleLayers, center, zoom
    """
    def post(self, request, *args, **kwargs):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
        from reportlab.lib.utils import ImageReader
        from django.http import HttpResponse
        from datetime import datetime
        import base64
        import io

        # Récupérer les données du POST
        title = request.data.get('title', 'Export Carte GreenSIG')
        map_image_base64 = request.data.get('mapImageBase64', '')
        visible_layers = request.data.get('visibleLayers', {})
        center = request.data.get('center', [0, 0])
        zoom = request.data.get('zoom', 15)

        # Créer le PDF en mémoire
        buffer = io.BytesIO()
        page_width, page_height = landscape(A4)
        pdf = canvas.Canvas(buffer, pagesize=landscape(A4))

        # Titre
        pdf.setFont("Helvetica-Bold", 20)
        pdf.drawString(2*cm, page_height - 2*cm, title)

        # Date
        pdf.setFont("Helvetica", 10)
        date_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        pdf.drawString(2*cm, page_height - 2.8*cm, f"Date d'export: {date_str}")

        # Image de la carte (si fournie)
        if map_image_base64:
            try:
                # Décoder l'image base64
                image_data = base64.b64decode(map_image_base64.split(',')[1] if ',' in map_image_base64 else map_image_base64)
                image = ImageReader(io.BytesIO(image_data))

                # Dessiner l'image (centré, 70% de la largeur)
                img_width = page_width * 0.7
                img_height = (page_height - 6*cm) * 0.7
                img_x = 2*cm
                img_y = page_height - 5*cm - img_height

                pdf.drawImage(image, img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True)
            except Exception as e:
                pdf.setFont("Helvetica", 10)
                pdf.drawString(2*cm, page_height - 5*cm, f"Erreur lors du chargement de l'image: {str(e)}")

        # Légende (à droite de l'image)
        legend_x = page_width - 6*cm
        legend_y = page_height - 4*cm

        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(legend_x, legend_y, "Légende")

        legend_y -= 0.7*cm
        pdf.setFont("Helvetica", 9)

        # Couleurs de légende (correspondant aux styles du frontend)
        layer_colors = {
            'sites': (59, 130, 246),      # #3b82f6
            'sousSites': (255, 165, 0),   # Orange (inchangé car pas dans constants.ts)
            'arbres': (34, 197, 94),      # #22c55e
            'gazons': (132, 204, 22),     # #84cc16
            'palmiers': (22, 163, 74),    # #16a34a
            'arbustes': (101, 163, 13),   # #65a30d
            'vivaces': (163, 230, 53),    # #a3e635
            'cactus': (77, 124, 15),      # #4d7c0f
            'graminees': (190, 242, 100), # #bef264
            'puits': (14, 165, 233),      # #0ea5e9
            'pompes': (6, 182, 212),      # #06b6d4
            'vannes': (20, 184, 166),     # #14b8a6
            'clapets': (8, 145, 178),     # #0891b2
            'canalisations': (2, 132, 199), # #0284c7
            'aspersions': (56, 189, 248), # #38bdf8
            'gouttes': (125, 211, 252),   # #7dd3fc
            'ballons': (3, 105, 161)      # #0369a1
        }

        layer_names = {
            'sites': 'Sites',
            'sousSites': 'Sous-sites',
            'arbres': 'Arbres',
            'gazons': 'Gazons',
            'palmiers': 'Palmiers',
            'arbustes': 'Arbustes',
            'vivaces': 'Vivaces',
            'cactus': 'Cactus',
            'graminees': 'Graminées',
            'puits': 'Puits',
            'pompes': 'Pompes',
            'vannes': 'Vannes',
            'clapets': 'Clapets',
            'canalisations': 'Canalisations',
            'aspersions': 'Aspersions',
            'gouttes': 'Goutte-à-goutte',
            'ballons': 'Ballons'
        }

        for layer_key, is_visible in visible_layers.items():
            if is_visible and layer_key in layer_colors:
                color = layer_colors[layer_key]
                pdf.setFillColorRGB(color[0]/255, color[1]/255, color[2]/255)
                pdf.circle(legend_x + 0.2*cm, legend_y, 0.15*cm, fill=1)

                pdf.setFillColorRGB(0, 0, 0)
                pdf.drawString(legend_x + 0.6*cm, legend_y - 0.15*cm, layer_names.get(layer_key, layer_key))
                legend_y -= 0.5*cm

        # Informations de la vue
        info_y = 2*cm
        pdf.setFont("Helvetica", 8)
        pdf.drawString(2*cm, info_y, f"Centre: [{center[0]:.6f}, {center[1]:.6f}] | Zoom: {zoom}")

        # Finaliser le PDF
        pdf.showPage()
        pdf.save()

        # Préparer la réponse
        buffer.seek(0)
        response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
        filename = f"carte_greensig_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response


# ==============================================================================
# VUE POUR LES STATISTIQUES
# ==============================================================================

class StatisticsView(APIView):
    """
    Vue pour retourner les statistiques globales du système.
    Retourne des statistiques contextuelles supplémentaires selon le rôle (CHEF_EQUIPE).
    """
    def get(self, request, *args, **kwargs):
        from django.db.models import Count, Avg, Sum, Max, Min, Q
        from django.apps import apps
        from django.utils import timezone
        
        # Statistiques globales (pour tout le monde)
        statistics = {
            # Statistiques de hiérarchie
            'hierarchy': {
                'total_sites': Site.objects.count(),
                'total_sous_sites': SousSite.objects.count(),
                'active_sites': Site.objects.filter(actif=True).count(),
            },

            # Statistiques végétaux
            'vegetation': {
                'arbres': {
                    'total': Arbre.objects.count(),
                    'by_taille': dict(Arbre.objects.values('taille').annotate(count=Count('id')).values_list('taille', 'count')),
                    'top_families': list(Arbre.objects.values('famille').annotate(count=Count('id')).order_by('-count')[:5].values('famille', 'count'))
                },
                'gazons': {
                    'total': Gazon.objects.count(),
                    'total_area_sqm': Gazon.objects.aggregate(Sum('area_sqm'))['area_sqm__sum'] or 0,
                },
                'palmiers': {
                    'total': Palmier.objects.count(),
                    'by_taille': dict(Palmier.objects.values('taille').annotate(count=Count('id')).values_list('taille', 'count')),
                },
                'arbustes': {
                    'total': Arbuste.objects.count(),
                    'avg_densite': Arbuste.objects.aggregate(Avg('densite'))['densite__avg'] or 0,
                },
                'vivaces': {
                    'total': Vivace.objects.count(),
                },
                'cactus': {
                    'total': Cactus.objects.count(),
                },
                'graminees': {
                    'total': Graminee.objects.count(),
                }
            },

            # Statistiques hydraulique
            'hydraulique': {
                'puits': {
                    'total': Puit.objects.count(),
                    'avg_profondeur': Puit.objects.aggregate(Avg('profondeur'))['profondeur__avg'] or 0,
                    'max_profondeur': Puit.objects.aggregate(Max('profondeur'))['profondeur__max'] or 0,
                },
                'pompes': {
                    'total': Pompe.objects.count(),
                    'avg_puissance': Pompe.objects.aggregate(Avg('puissance'))['puissance__avg'] or 0,
                    'avg_debit': Pompe.objects.aggregate(Avg('debit'))['debit__avg'] or 0,
                },
                'vannes': {
                    'total': Vanne.objects.count(),
                },
                'clapets': {
                    'total': Clapet.objects.count(),
                },
                'canalisations': {
                    'total': Canalisation.objects.count(),
                },
                'aspersions': {
                    'total': Aspersion.objects.count(),
                },
                'gouttes': {
                    'total': Goutte.objects.count(),
                },
                'ballons': {
                    'total': Ballon.objects.count(),
                    'total_volume': Ballon.objects.aggregate(Sum('volume'))['volume__sum'] or 0,
                }
            },

            # Statistiques globales
            'global': {
                'total_objets': (
                    Arbre.objects.count() + Gazon.objects.count() + Palmier.objects.count() +
                    Arbuste.objects.count() + Vivace.objects.count() + Cactus.objects.count() +
                    Graminee.objects.count() + Puit.objects.count() + Pompe.objects.count() +
                    Vanne.objects.count() + Clapet.objects.count() + Canalisation.objects.count() +
                    Aspersion.objects.count() + Goutte.objects.count() + Ballon.objects.count()
                ),
                'total_vegetation': (
                    Arbre.objects.count() + Gazon.objects.count() + Palmier.objects.count() +
                    Arbuste.objects.count() + Vivace.objects.count() + Cactus.objects.count() +
                    Graminee.objects.count()
                ),
                'total_hydraulique': (
                    Puit.objects.count() + Pompe.objects.count() + Vanne.objects.count() +
                    Clapet.objects.count() + Canalisation.objects.count() + Aspersion.objects.count() +
                    Goutte.objects.count() + Ballon.objects.count()
                )
            }
        }
        
        # --- LOGIQUE SPÉCIFIQUE POUR CHEF D'ÉQUIPE ---
        user = request.user
        if user.is_authenticated:
            is_chef = user.roles_utilisateur.filter(role__nom_role='CHEF_EQUIPE').exists()
            if is_chef:
                try:
                    Tache = apps.get_model('api_planification', 'Tache')
                    Equipe = apps.get_model('api_users', 'Equipe')
                    Absence = apps.get_model('api_users', 'Absence')
                    
                    # Récupérer l'opérateur lié
                    operateur = getattr(user, 'operateur_profile', None)
                    if operateur:
                        # Ses équipes
                        mes_equipes_ids = Equipe.objects.filter(chef_equipe=operateur, actif=True).values_list('id', flat=True)
                        
                        # Tâches de ses équipes
                        mes_taches = Tache.objects.filter(
                            Q(equipes__id__in=mes_equipes_ids) | Q(id_equipe__in=mes_equipes_ids),
                            deleted_at__isnull=True
                        ).distinct()
                        
                        # Absences dans ses équipes (membres)
                        # Récupérer tous les membres de ses équipes
                        membres_ids = set()
                        for eq in Equipe.objects.filter(id__in=mes_equipes_ids):
                            membres_ids.update(eq.membres.values_list('id', flat=True))
                        
                        today = timezone.now().date()
                        absences_today = Absence.objects.filter(
                            employe__id__in=membres_ids,
                            date_debut__lte=today,
                            date_fin__gte=today,
                            statut='VALIDEE'
                        ).count()
                        
                        statistics['chef_equipe_stats'] = {
                            'taches_today': mes_taches.filter(date_debut_planifiee__date=today).count(),
                            'taches_en_cours': mes_taches.filter(statut='EN_COURS').count(),
                            'taches_a_faire': mes_taches.filter(statut='A_FAIRE').count(),
                            'taches_retard': mes_taches.filter(statut='EN_RETARD').count(), 
                            'absences_today': absences_today,
                            'equipes_count': len(mes_equipes_ids)
                        }
                except Exception as e:
                    print(f"Error calculating chef equipe stats: {e}")
                    # Ne pas bloquer la réponse si erreur dans les stats spécifiques

        return Response(statistics)


# ==============================================================================
# VUES POUR L'EXPORT DE DONNÉES
# ==============================================================================

class ExportDataView(APIView):
    """
    Vue générique pour exporter les données en CSV, Excel, GeoJSON, KML ou Shapefile.
    Paramètres de requête:
    - model: nom du modèle (arbres, gazons, palmiers, etc.)
    - format: csv, xlsx, geojson, kml, shp (défaut: csv)
    - ids: optionnel, liste d'IDs séparés par virgules pour export sélectif
    - filtres: optionnels (même syntaxe que les endpoints de liste)
    """

    MODEL_MAPPING = {
        'sites': Site,
        'sous-sites': SousSite,
        'arbres': Arbre,
        'gazons': Gazon,
        'palmiers': Palmier,
        'arbustes': Arbuste,
        'vivaces': Vivace,
        'cactus': Cactus,
        'graminees': Graminee,
        'puits': Puit,
        'pompes': Pompe,
        'vannes': Vanne,
        'clapets': Clapet,
        'canalisations': Canalisation,
        'aspersions': Aspersion,
        'gouttes': Goutte,
        'ballons': Ballon,
    }

    def get(self, request, model_name, *args, **kwargs):
        import csv
        from openpyxl import Workbook
        from django.http import HttpResponse
        from datetime import datetime

        # Vérifier que le modèle existe
        if model_name not in self.MODEL_MAPPING:
            return Response({'error': f'Modèle invalide: {model_name}'}, status=400)

        model_class = self.MODEL_MAPPING[model_name]

        # Récupérer le format d'export
        export_format = request.query_params.get('format', 'csv').lower()
        valid_formats = ['csv', 'xlsx', 'geojson', 'kml', 'shp', 'shapefile']
        if export_format not in valid_formats:
            return Response({'error': f'Format invalide. Utilisez: {", ".join(valid_formats)}'}, status=400)

        # Normaliser shapefile
        if export_format == 'shapefile':
            export_format = 'shp'

        # Appliquer les filtres
        queryset = model_class.objects.all()

        # Filtre par IDs si fourni
        ids_param = request.query_params.get('ids', '')
        if ids_param:
            try:
                ids = [int(id.strip()) for id in ids_param.split(',') if id.strip()]
                queryset = queryset.filter(pk__in=ids)
            except ValueError:
                return Response({'error': 'ids parameter must be comma-separated integers'}, status=400)

        # Filtre par site si fourni
        site_id = request.query_params.get('site')
        if site_id:
            queryset = queryset.filter(site_id=site_id)

        # Vérifier qu'il y a des données
        if not queryset.exists():
            return Response({'error': 'Aucune donnée à exporter'}, status=404)

        # ==============================================================================
        # EXPORT GeoJSON
        # ==============================================================================
        if export_format == 'geojson':
            from .services.geo_io import export_to_geojson

            geojson_data = export_to_geojson(queryset)

            response = HttpResponse(
                json.dumps(geojson_data, ensure_ascii=False, indent=2),
                content_type='application/geo+json; charset=utf-8'
            )
            filename = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        # ==============================================================================
        # EXPORT KML
        # ==============================================================================
        if export_format == 'kml':
            from .services.geo_io import export_to_kml

            kml_content = export_to_kml(queryset)

            response = HttpResponse(
                kml_content,
                content_type='application/vnd.google-earth.kml+xml; charset=utf-8'
            )
            filename = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.kml"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        # ==============================================================================
        # EXPORT Shapefile (ZIP)
        # ==============================================================================
        if export_format == 'shp':
            from .services.geo_io import export_to_shapefile

            try:
                zip_content = export_to_shapefile(queryset, model_name)

                response = HttpResponse(
                    zip_content,
                    content_type='application/zip'
                )
                filename = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            except ImportError as e:
                return Response({'error': str(e)}, status=500)
            except Exception as e:
                return Response({'error': f'Shapefile export error: {str(e)}'}, status=500)

        # ==============================================================================
        # EXPORT CSV / XLSX (original logic)
        # ==============================================================================
        # Récupérer tous les objets (pas de pagination pour l'export)
        objects = list(queryset.values())

        # Obtenir les noms de colonnes
        field_names = list(objects[0].keys())

        # Export CSV
        if export_format == 'csv':
            response = HttpResponse(content_type='text/csv; charset=utf-8')
            filename = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            # Ajouter le BOM UTF-8 pour Excel
            response.write('\ufeff')

            writer = csv.DictWriter(response, fieldnames=field_names)
            writer.writeheader()
            writer.writerows(objects)

            return response

        # Export Excel
        elif export_format == 'xlsx':
            wb = Workbook()
            ws = wb.active
            ws.title = model_name[:31]  # Excel limite à 31 caractères

            # Écrire l'en-tête
            ws.append(field_names)

            # Écrire les données
            for obj in objects:
                ws.append([obj[field] for field in field_names])

            # Ajuster la largeur des colonnes
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(cell.value)
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width

            # Sauvegarder dans un buffer
            from io import BytesIO
            buffer = BytesIO()
            wb.save(buffer)
            buffer.seek(0)

            response = HttpResponse(
                buffer.getvalue(),
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'

            return response


# ==============================================================================
# VUE INVENTAIRE UNIFIÉE (15 types combinés)
# ==============================================================================

class InventoryListView(APIView):
    """
    Vue unifiée qui retourne tous les objets (15 types combinés).
    Compatible avec le frontend GreenSIGV1 qui attend un endpoint unique /api/inventory/.

    Cette vue utilise le polymorphisme de la classe Objet pour agréger
    automatiquement tous les types d'objets (Arbre, Gazon, Puit, etc.).

    Endpoint: GET /api/inventory/

    Query params optionnels:
    - type: filtrer par type ('Arbre', 'Gazon', 'Puit', etc.)
    - site: filtrer par site ID ou liste d'IDs séparés par virgule
    - state: filtrer par état (bon, moyen, mauvais, critique) - liste séparée par virgule
    - search: recherche textuelle
    - page: numéro de page (pagination 50 items)
    
    Filtres par plages numériques:
    - surface_min, surface_max: plage de surface en m²
    - diameter_min, diameter_max: plage de diamètre en cm
    - depth_min, depth_max: plage de profondeur en m
    - density_min, density_max: plage de densité
    
    Filtres par date:
    - last_intervention_start, last_intervention_end: plage de dates (YYYY-MM-DD)
    - never_intervened: true/false - objets jamais intervenus
    - urgent_maintenance: true/false - objets nécessitant maintenance urgente (> 6 mois)
    
    Filtres spécifiques:
    - family: famille botanique (liste séparée par virgule)
    - size: taille (Petit, Moyen, Grand) - liste séparée par virgule
    - material: matériau (liste séparée par virgule)
    - equipment_type: type d'équipement (liste séparée par virgule)

    Returns:
        {
            "count": 450,
            "next": "url_page_suivante",
            "previous": null,
            "results": [...]
        }
    """

    def get(self, request):
        """
        Méthode GET optimisée: interroge directement les modèles enfants
        au lieu de passer par Objet, ce qui évite les itérations Python.
        """
        from rest_framework.pagination import PageNumberPagination
        from datetime import timedelta
        from django.utils import timezone
        from itertools import chain

        # Mapping des types vers les modèles et serializers
        MODEL_MAP = {
            'arbre': (Arbre, ArbreSerializer),
            'palmier': (Palmier, PalmierSerializer),
            'gazon': (Gazon, GazonSerializer),
            'arbuste': (Arbuste, ArbusteSerializer),
            'vivace': (Vivace, VivaceSerializer),
            'cactus': (Cactus, CactusSerializer),
            'graminee': (Graminee, GramineeSerializer),
            'puit': (Puit, PuitSerializer),
            'pompe': (Pompe, PompeSerializer),
            'vanne': (Vanne, VanneSerializer),
            'clapet': (Clapet, ClapetSerializer),
            'canalisation': (Canalisation, CanalisationSerializer),
            'aspersion': (Aspersion, AspersionSerializer),
            'goutte': (Goutte, GoutteSerializer),
            'ballon': (Ballon, BallonSerializer),
        }

        # Paramètres de filtrage
        type_filter = request.query_params.get('type', None)
        site_filter = request.query_params.get('site', None)
        etat_filter = request.query_params.get('etat', None)
        famille_filter = request.query_params.get('famille', None)
        search_query = request.query_params.get('search', '').strip()

        # Filtres de date
        never_intervened = request.query_params.get('never_intervened', '').lower() == 'true'
        urgent_maintenance = request.query_params.get('urgent_maintenance', '').lower() == 'true'
        last_intervention_start = request.query_params.get('last_intervention_start', None)

        # Déterminer quels types interroger
        if type_filter:
            target_types = [t.strip().lower() for t in type_filter.split(',')]
            # Normaliser 'graminée' -> 'graminee'
            target_types = ['graminee' if t == 'graminée' else t for t in target_types]
        else:
            target_types = list(MODEL_MAP.keys())

        # Filtrer par rôle client si nécessaire
        user = request.user
        client_filter = None
        if user.is_authenticated:
            has_client_role = user.roles_utilisateur.filter(role__nom_role='CLIENT').exists()
            if has_client_role and hasattr(user, 'client_profile'):
                client_filter = user.client_profile

        # Collecter les résultats de chaque type
        all_results = []

        for type_name in target_types:
            if type_name not in MODEL_MAP:
                continue

            model_class, serializer_class = MODEL_MAP[type_name]

            # Construire le queryset avec select_related pour éviter les N+1
            qs = model_class.objects.select_related('site', 'sous_site')

            # Appliquer les filtres au niveau de la base de données
            if client_filter:
                qs = qs.filter(site__client=client_filter)

            if site_filter:
                qs = qs.filter(site_id=site_filter)

            if etat_filter:
                qs = qs.filter(etat=etat_filter)

            # Filtre famille (pour les types qui ont ce champ)
            if famille_filter and hasattr(model_class, 'famille'):
                qs = qs.filter(famille__icontains=famille_filter)

            # Filtre recherche
            if search_query:
                q = Q(site__nom_site__icontains=search_query) | Q(site__code_site__icontains=search_query)
                if hasattr(model_class, 'nom'):
                    q |= Q(nom__icontains=search_query)
                if hasattr(model_class, 'famille'):
                    q |= Q(famille__icontains=search_query)
                if hasattr(model_class, 'marque'):
                    q |= Q(marque__icontains=search_query)
                if hasattr(model_class, 'type'):
                    q |= Q(type__icontains=search_query)
                qs = qs.filter(q)

            # Filtres de date d'intervention
            if hasattr(model_class, 'last_intervention_date'):
                if never_intervened:
                    qs = qs.filter(last_intervention_date__isnull=True)
                if urgent_maintenance:
                    six_months_ago = timezone.now().date() - timedelta(days=180)
                    qs = qs.filter(last_intervention_date__lt=six_months_ago)
                if last_intervention_start:
                    qs = qs.filter(last_intervention_date__gte=last_intervention_start)

            # Limiter le nombre d'objets récupérés pour éviter les timeout
            qs = qs.order_by('id')

            # Ajouter au résultat avec le type
            for obj in qs:
                all_results.append((obj, type_name.capitalize(), serializer_class))

        # Trier par ID pour un ordre cohérent
        all_results.sort(key=lambda x: x[0].id)

        # Pagination - d'abord sur les objets, puis sérialisation
        paginator = PageNumberPagination()
        paginator.page_size = 50

        page_size_param = request.query_params.get('page_size', None)
        if page_size_param:
            try:
                paginator.page_size = int(page_size_param)
            except ValueError:
                pass

        # Créer une structure paginable (liste d'objets)
        total_count = len(all_results)

        # Calculer la page manuellement pour éviter de tout sérialiser
        page_num = int(request.query_params.get('page', 1))
        start_idx = (page_num - 1) * paginator.page_size
        end_idx = start_idx + paginator.page_size

        page_items = all_results[start_idx:end_idx]

        # Sérialiser uniquement les éléments de la page
        serialized_results = []
        for obj, type_name, serializer_class in page_items:
            serializer = serializer_class(obj)
            data = serializer.data
            if 'properties' in data:
                data['properties']['object_type'] = type_name
            serialized_results.append(data)

        # Construire la réponse paginée
        base_url = request.build_absolute_uri().split('?')[0]
        query_params = request.query_params.copy()

        next_url = None
        if end_idx < total_count:
            query_params['page'] = page_num + 1
            next_url = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in query_params.items())}"

        previous_url = None
        if page_num > 1:
            query_params['page'] = page_num - 1
            previous_url = f"{base_url}?{'&'.join(f'{k}={v}' for k, v in query_params.items())}"

        return Response({
            'count': total_count,
            'next': next_url,
            'previous': previous_url,
            'results': serialized_results
        })

    def apply_id_filter(self, queryset, request):
        """Filtre par ID d'objet (pour récupérer un objet spécifique)"""
        object_id = request.query_params.get('id', None)
        if object_id:
            try:
                queryset = queryset.filter(id=int(object_id))
            except ValueError:
                pass  # Ignore invalid ID
        return queryset

    def apply_type_filter(self, queryset, request):
        """Filtre par type d'objet"""
        type_filter = request.query_params.get('type', None)
        if type_filter:
            types = [t.lower().strip() for t in type_filter.split(',')]
            objets_ids = []
            for obj in queryset:
                for t in types:
                    if t == 'graminée': t = 'graminee'
                    if hasattr(obj, t):
                        objets_ids.append(obj.id)
                        break
            queryset = queryset.filter(id__in=objets_ids)
        return queryset

    def apply_site_filter(self, queryset, request):
        """Filtre par site (supporte liste d'IDs)"""
        site_filter = request.query_params.get('site', None)
        if site_filter:
            site_ids = [int(s.strip()) for s in site_filter.split(',') if s.strip().isdigit()]
            if site_ids:
                queryset = queryset.filter(site_id__in=site_ids)
        return queryset

    def apply_state_filter(self, queryset, request):
        """Filtre par état (supporte liste)"""
        state_filter = request.query_params.get('state', None)
        if state_filter:
            states = [s.strip() for s in state_filter.split(',')]
            queryset = queryset.filter(etat__in=states)
        return queryset

    def apply_search_filter(self, queryset, request):
        """Filtre par recherche textuelle"""
        search_query = request.query_params.get('search', '').strip()
        if search_query:
            q_search = Q()
            q_search |= Q(site__nom_site__icontains=search_query)
            q_search |= Q(site__code_site__icontains=search_query)
            q_search |= Q(sous_site__nom__icontains=search_query)

            for model_name in ['arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee']:
                q_search |= Q(**{f"{model_name}__nom__icontains": search_query})
                q_search |= Q(**{f"{model_name}__famille__icontains": search_query})
            
            for model_name in ['puit', 'pompe']:
                q_search |= Q(**{f"{model_name}__nom__icontains": search_query})

            for model_name in ['vanne', 'clapet', 'canalisation', 'aspersion', 'ballon']:
                q_search |= Q(**{f"{model_name}__marque__icontains": search_query})
            
            q_search |= Q(goutte__type__icontains=search_query)
            queryset = queryset.filter(q_search)
        return queryset

    def apply_range_filters(self, queryset, request):
        """Filtre par plages numériques (surface, diamètre, profondeur, densité)"""
        # Surface (Gazon uniquement)
        surface_min = request.query_params.get('surface_min')
        surface_max = request.query_params.get('surface_max')
        if surface_min or surface_max:
            q = Q()
            if surface_min:
                q &= Q(gazon__area_sqm__gte=float(surface_min))
            if surface_max:
                q &= Q(gazon__area_sqm__lte=float(surface_max))
            queryset = queryset.filter(q)

        # Diamètre (Puit, Pompe, équipements hydrauliques)
        diameter_min = request.query_params.get('diameter_min')
        diameter_max = request.query_params.get('diameter_max')
        if diameter_min or diameter_max:
            q = Q()
            for model in ['puit', 'pompe', 'vanne', 'clapet', 'canalisation', 'aspersion', 'goutte']:
                if diameter_min:
                    q |= Q(**{f"{model}__diametre__gte": float(diameter_min)})
                if diameter_max:
                    q |= Q(**{f"{model}__diametre__lte": float(diameter_max)})
            queryset = queryset.filter(q)

        # Profondeur (Puit uniquement)
        depth_min = request.query_params.get('depth_min')
        depth_max = request.query_params.get('depth_max')
        if depth_min or depth_max:
            q = Q()
            if depth_min:
                q &= Q(puit__profondeur__gte=float(depth_min))
            if depth_max:
                q &= Q(puit__profondeur__lte=float(depth_max))
            queryset = queryset.filter(q)

        # Densité (Arbuste, Vivace, Cactus, Graminee)
        density_min = request.query_params.get('density_min')
        density_max = request.query_params.get('density_max')
        if density_min or density_max:
            q = Q()
            for model in ['arbuste', 'vivace', 'cactus', 'graminee']:
                if density_min:
                    q |= Q(**{f"{model}__densite__gte": float(density_min)})
                if density_max:
                    q |= Q(**{f"{model}__densite__lte": float(density_max)})
            queryset = queryset.filter(q)

        return queryset

    def apply_date_filters(self, queryset, request):
        """Filtre par dates d'intervention"""
        from datetime import timedelta
        from django.utils import timezone

        start_date = request.query_params.get('last_intervention_start')
        end_date = request.query_params.get('last_intervention_end')
        never_intervened = request.query_params.get('never_intervened', '').lower() == 'true'
        urgent = request.query_params.get('urgent_maintenance', '').lower() == 'true'

        # Jamais intervenu
        if never_intervened:
            q = Q()
            for model in ['arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee', 'puit', 'pompe']:
                q |= Q(**{f"{model}__last_intervention_date__isnull": True})
            queryset = queryset.filter(q)

        # Maintenance urgente (> 6 mois)
        if urgent:
            six_months_ago = timezone.now().date() - timedelta(days=180)
            q = Q()
            for model in ['arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee', 'puit', 'pompe']:
                q |= Q(**{f"{model}__last_intervention_date__lt": six_months_ago})
            queryset = queryset.filter(q)

        # Plage de dates personnalisée
        if start_date:
            q = Q()
            for model in ['arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee', 'puit', 'pompe']:
                q |= Q(**{f"{model}__last_intervention_date__gte": start_date})
            queryset = queryset.filter(q)

        if end_date:
            q = Q()
            for model in ['arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee', 'puit', 'pompe']:
                q |= Q(**{f"{model}__last_intervention_date__lte": end_date})
            queryset = queryset.filter(q)

        return queryset

    def apply_specific_filters(self, queryset, request):
        """Filtre par attributs spécifiques (famille, taille, matériau, type)"""
        # Famille (végétaux)
        family_filter = request.query_params.get('family')
        if family_filter:
            families = [f.strip() for f in family_filter.split(',')]
            q = Q()
            for model in ['arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee']:
                q |= Q(**{f"{model}__famille__in": families})
            queryset = queryset.filter(q)

        # Taille (Arbre, Palmier)
        size_filter = request.query_params.get('size')
        if size_filter:
            sizes = [s.strip() for s in size_filter.split(',')]
            q = Q(arbre__taille__in=sizes) | Q(palmier__taille__in=sizes)
            queryset = queryset.filter(q)

        # Matériau (équipements hydrauliques)
        material_filter = request.query_params.get('material')
        if material_filter:
            materials = [m.strip() for m in material_filter.split(',')]
            q = Q()
            for model in ['vanne', 'clapet', 'canalisation', 'aspersion', 'goutte', 'ballon']:
                q |= Q(**{f"{model}__materiau__in": materials})
            queryset = queryset.filter(q)

        # Type d'équipement (Pompe, équipements hydrauliques)
        equipment_type_filter = request.query_params.get('equipment_type')
        if equipment_type_filter:
            types = [t.strip() for t in equipment_type_filter.split(',')]
            q = Q()
            for model in ['pompe', 'vanne', 'clapet', 'canalisation', 'aspersion', 'goutte']:
                q |= Q(**{f"{model}__type__in": types})
            queryset = queryset.filter(q)

        return queryset

    def _get_serializer_class(self, objet):
        """
        Retourne le serializer approprié selon le type de l'objet.

        Args:
            objet: Instance de Arbre, Gazon, Puit, etc.

        Returns:
            Serializer class correspondant au type
        """
        type_mapping = {
            'Arbre': ArbreSerializer,
            'Gazon': GazonSerializer,
            'Palmier': PalmierSerializer,
            'Arbuste': ArbusteSerializer,
            'Vivace': VivaceSerializer,
            'Cactus': CactusSerializer,
            'Graminee': GramineeSerializer,
            'Puit': PuitSerializer,
            'Pompe': PompeSerializer,
            'Vanne': VanneSerializer,
            'Clapet': ClapetSerializer,
            'Canalisation': CanalisationSerializer,
            'Aspersion': AspersionSerializer,
            'Goutte': GoutteSerializer,
            'Ballon': BallonSerializer,
        }
        return type_mapping.get(objet.__class__.__name__, ArbreSerializer)


# ==============================================================================
# ENDPOINT POUR LES OPTIONS DE FILTRAGE
# ==============================================================================

class FilterOptionsView(APIView):
    """
    Endpoint pour récupérer les options disponibles pour les filtres.
    
    Endpoint: GET /api/inventory/filter-options/
    
    Query params optionnels:
    - type: filtrer les options par type d'objet (ex: 'Arbre', 'Puit')
    
    Returns:
        {
            "sites": [{"id": 1, "name": "Jardin Majorelle"}, ...],
            "zones": ["Zone A", "Villa 1", ...],
            "families": ["Palmaceae", "Rosaceae", ...],
            "materials": ["PVC", "Acier", ...],
            "equipment_types": ["Centrifuge", "Immergée", ...],
            "sizes": ["Petit", "Moyen", "Grand"],
            "states": ["bon", "moyen", "mauvais", "critique"],
            "ranges": {
                "surface": [0, 5000],
                "diameter": [0, 200],
                "depth": [0, 150],
                "density": [0, 100]
            }
        }
    """
    
    def get(self, request):
        from django.db.models import Min, Max
        from django.core.cache import cache
        from django.utils.encoding import force_str
        
        object_type = request.query_params.get('type', '').strip()
        
        # Créer une clé de cache basée sur le type d'objet
        cache_key = f'filter_options_{object_type or "all"}'
        
        # Essayer de récupérer depuis le cache (5 minutes)
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)
        
        # Sites (toujours tous) - optimisé avec only()
        sites = Site.objects.filter(actif=True).only('id', 'nom_site').order_by('nom_site')
        sites_list = [{'id': s.id, 'name': s.nom_site} for s in sites]
        
        # Zones (sous-sites)
        zones = SousSite.objects.values_list('nom', flat=True).distinct().order_by('nom')
        zones_list = [z for z in zones if z]
        
        # États (depuis ETAT_CHOICES)
        from .models import ETAT_CHOICES
        states_list = [choice[0] for choice in ETAT_CHOICES]
        
        # Tailles (depuis TAILLE_CHOICES)
        from .models import TAILLE_CHOICES
        sizes_list = [choice[0] for choice in TAILLE_CHOICES]
        
        # Familles botaniques (végétaux)
        families = set()
        if not object_type or object_type.lower() in ['arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee']:
            for model in [Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee]:
                model_families = model.objects.values_list('famille', flat=True).distinct()
                families.update([f for f in model_families if f])
        families_list = sorted(list(families))
        
        # Matériaux (équipements hydrauliques)
        materials = set()
        if not object_type or object_type.lower() in ['vanne', 'clapet', 'canalisation', 'aspersion', 'goutte', 'ballon']:
            for model in [Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon]:
                if hasattr(model, 'materiau'):
                    model_materials = model.objects.values_list('materiau', flat=True).distinct()
                    materials.update([m for m in model_materials if m])
        materials_list = sorted(list(materials))
        
        # Types d'équipements (hydraulique)
        equipment_types = set()
        if not object_type or object_type.lower() in ['pompe', 'vanne', 'clapet', 'canalisation', 'aspersion', 'goutte']:
            for model in [Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte]:
                if hasattr(model, 'type'):
                    model_types = model.objects.values_list('type', flat=True).distinct()
                    equipment_types.update([t for t in model_types if t])
        equipment_types_list = sorted(list(equipment_types))
        
        # Plages de valeurs
        ranges = {}
        
        # Surface (Gazon)
        if not object_type or object_type.lower() == 'gazon':
            surface_range = Gazon.objects.aggregate(
                min=Min('area_sqm'),
                max=Max('area_sqm')
            )
            ranges['surface'] = [
                float(surface_range['min'] or 0),
                float(surface_range['max'] or 0)
            ]
        
        # Diamètre (Puit, Pompe, équipements hydrauliques)
        if not object_type or object_type.lower() in ['puit', 'pompe', 'vanne', 'clapet', 'canalisation', 'aspersion', 'goutte']:
            diameter_values = []
            for model in [Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte]:
                if hasattr(model, 'diametre'):
                    model_range = model.objects.aggregate(
                        min=Min('diametre'),
                        max=Max('diametre')
                    )
                    if model_range['min'] is not None:
                        diameter_values.append(float(model_range['min']))
                    if model_range['max'] is not None:
                        diameter_values.append(float(model_range['max']))
            
            if diameter_values:
                ranges['diameter'] = [min(diameter_values), max(diameter_values)]
            else:
                ranges['diameter'] = [0, 0]
        
        # Profondeur (Puit)
        if not object_type or object_type.lower() == 'puit':
            depth_range = Puit.objects.aggregate(
                min=Min('profondeur'),
                max=Max('profondeur')
            )
            ranges['depth'] = [
                float(depth_range['min'] or 0),
                float(depth_range['max'] or 0)
            ]
        
        # Densité (Arbuste, Vivace, Cactus, Graminee)
        if not object_type or object_type.lower() in ['arbuste', 'vivace', 'cactus', 'graminee']:
            density_values = []
            for model in [Arbuste, Vivace, Cactus, Graminee]:
                if hasattr(model, 'densite'):
                    model_range = model.objects.aggregate(
                        min=Min('densite'),
                        max=Max('densite')
                    )
                    if model_range['min'] is not None:
                        density_values.append(float(model_range['min']))
                    if model_range['max'] is not None:
                        density_values.append(float(model_range['max']))
            
            if density_values:
                ranges['density'] = [min(density_values), max(density_values)]
            else:
                ranges['density'] = [0, 0]
        
        response_data = {
            'sites': sites_list,
            'zones': zones_list,
            'families': families_list,
            'materials': materials_list,
            'equipment_types': equipment_types_list,
            'sizes': sizes_list,
            'states': states_list,
            'ranges': ranges
        }
        
        # Mettre en cache pour 5 minutes (300 secondes)
        cache.set(cache_key, response_data, 300)
        
        return Response(response_data)


# ==============================================================================
# ENDPOINT UNIFIÉ POUR LA CARTE (avec Bounding Box)
# ==============================================================================

class MapObjectsView(APIView):
    """
    Endpoint unique et intelligent pour charger tous les objets de la carte.

    Permissions automatiques basées sur le rôle:
    - ADMIN: voit tout
    - CLIENT: voit uniquement ses sites et objets
    - CHEF_EQUIPE: voit uniquement les sites/objets liés aux tâches de ses équipes

    Endpoint: GET /api/map/

    Query params:
    - bbox: Bounding box au format "west,south,east,north" (ex: "-7.95,32.20,-7.90,32.25")
    - types: Liste des types à charger (ex: "sites,arbres,gazons")
    - zoom: Niveau de zoom (pour optimisations futures)

    Returns:
        {
            "type": "FeatureCollection",
            "features": [...],
            "count": 150,
            "bbox_used": true
        }
    """

    def get(self, request):
        from django.contrib.gis.geos import Polygon

        # Paramètres
        bbox_str = request.GET.get('bbox')
        types_str = request.GET.get('types', '')
        zoom = int(request.GET.get('zoom', 10))

        requested_types = [t.strip().lower() for t in types_str.split(',') if t.strip()]

        results = []

        # Déterminer les permissions basées sur le rôle
        user = request.user
        is_admin = False
        client_filter = None
        chef_equipe_filter = None  # (site_ids, object_ids)

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            if 'ADMIN' in roles:
                is_admin = True
            elif 'CLIENT' in roles and hasattr(user, 'client_profile'):
                client_filter = user.client_profile
            elif 'CHEF_EQUIPE' in roles:
                chef_equipe_filter = self._get_chef_equipe_filters(user)

        # ==============================================================================
        # 1. CHARGER LES SITES (toujours tous car peu nombreux)
        # ==============================================================================
        if not requested_types or 'sites' in requested_types:
            sites = Site.objects.filter(actif=True).order_by('id')

            # Appliquer les filtres de permissions
            if not is_admin:
                if client_filter:
                    sites = sites.filter(client=client_filter)
                elif chef_equipe_filter:
                    site_ids, _ = chef_equipe_filter
                    if site_ids:
                        sites = sites.filter(id__in=site_ids)
                    else:
                        sites = sites.none()

            for site in sites:
                # Utiliser le centroid pré-calculé (ou calculer depuis geometrie_emprise)
                centroid = site.centroid or site.geometrie_emprise.centroid

                serializer = SiteSerializer(site)
                feature = serializer.data

                # Ajouter des métadonnées pour le frontend
                feature['properties']['object_type'] = 'Site'
                feature['properties']['center'] = {
                    'lat': centroid.y,
                    'lng': centroid.x
                }

                results.append(feature)

        # ==============================================================================
        # 2. CHARGER VÉGÉTATION / HYDRAULIQUE (avec bbox si fourni)
        # ==============================================================================
        if bbox_str:
            try:
                west, south, east, north = map(float, bbox_str.split(','))
                bbox_polygon = Polygon.from_bbox((west, south, east, north))

                # Mapping type -> (model, serializer)
                type_mapping = {
                    'arbres': (Arbre, ArbreSerializer),
                    'gazons': (Gazon, GazonSerializer),
                    'palmiers': (Palmier, PalmierSerializer),
                    'arbustes': (Arbuste, ArbusteSerializer),
                    'vivaces': (Vivace, VivaceSerializer),
                    'cactus': (Cactus, CactusSerializer),
                    'graminees': (Graminee, GramineeSerializer),
                    'puits': (Puit, PuitSerializer),
                    'pompes': (Pompe, PompeSerializer),
                    'vannes': (Vanne, VanneSerializer),
                    'clapets': (Clapet, ClapetSerializer),
                    'canalisations': (Canalisation, CanalisationSerializer),
                    'aspersions': (Aspersion, AspersionSerializer),
                    'gouttes': (Goutte, GoutteSerializer),
                    'ballons': (Ballon, BallonSerializer),
                }

                # Déterminer quels types charger
                types_to_load = requested_types if requested_types else list(type_mapping.keys())

                # Types polygones qui nécessitent le calcul de superficie
                polygon_types = {'gazons', 'arbustes', 'vivaces', 'cactus', 'graminees'}

                # Charger chaque type avec filtrage bbox
                for type_name in types_to_load:
                    if type_name in type_mapping:
                        Model, Serializer = type_mapping[type_name]

                        # Query avec bbox filter
                        queryset = Model.objects.filter(
                            geometry__intersects=bbox_polygon
                        ).select_related('site', 'sous_site')

                        # OPTIMISÉ: Pré-calculer la superficie pour les types polygones
                        # Évite N+1 requêtes ST_Area dans le serializer
                        if type_name in polygon_types:
                            from django.db.models.expressions import RawSQL
                            queryset = queryset.annotate(
                                _superficie_annotee=RawSQL(
                                    "ST_Area(geometry::geography)",
                                    []
                                )
                            )

                        # Appliquer les filtres de permissions (sauf pour ADMIN)
                        if not is_admin:
                            if client_filter:
                                queryset = queryset.filter(site__client=client_filter)
                            elif chef_equipe_filter:
                                _, object_ids = chef_equipe_filter
                                # CHEF_EQUIPE: ne voir QUE les objets directement liés aux tâches
                                if object_ids:
                                    queryset = queryset.filter(objet_ptr_id__in=object_ids)
                                else:
                                    queryset = queryset.none()

                        queryset = queryset.order_by('id')[:100]  # 100 par type max

                        # Serializer chaque objet
                        for obj in queryset:
                            serializer = Serializer(obj)
                            feature = serializer.data
                            feature['properties']['object_type'] = Model.__name__
                            results.append(feature)

            except (ValueError, AttributeError) as e:
                return Response({
                    'error': f'Invalid bbox format: {str(e)}'
                }, status=400)

        return Response({
            'type': 'FeatureCollection',
            'features': results,
            'count': len(results),
            'bbox_used': bbox_str is not None,
            'zoom': zoom
        })

    def _get_chef_equipe_filters(self, user):
        """
        Récupère les IDs des sites et objets liés aux tâches du chef d'équipe.
        Returns: tuple (site_ids, object_ids)

        Le chef d'équipe voit:
        - Les sites qui contiennent les objets de ses tâches
        - Uniquement les objets directement liés à ses tâches

        OPTIMISÉ: Une seule requête SQL au lieu de N+1.
        """
        from api_users.models import Equipe
        from api_planification.models import Tache

        try:
            operateur = user.operateur_profile
            # Équipes gérées par ce chef d'équipe
            equipes_gerees_ids = list(Equipe.objects.filter(
                chef_equipe=operateur,
                actif=True
            ).values_list('id', flat=True))

            if not equipes_gerees_ids:
                return ([], [])

            # Tâches assignées à ces équipes (non supprimées) - juste les IDs
            taches_ids = Tache.objects.filter(
                deleted_at__isnull=True
            ).filter(
                Q(equipes__id__in=equipes_gerees_ids) | Q(id_equipe__in=equipes_gerees_ids)
            ).values_list('id', flat=True).distinct()

            # OPTIMISÉ: Récupérer les objets en une seule requête via la relation inverse
            objets_data = Objet.objects.filter(
                taches__id__in=taches_ids
            ).values_list('id', 'site_id').distinct()

            # Extraire les IDs d'objets et de sites
            object_ids = []
            site_ids = []
            for obj_id, site_id in objets_data:
                object_ids.append(obj_id)
                if site_id:
                    site_ids.append(site_id)

            return (list(set(site_ids)), object_ids)
        except Exception:
            return ([], [])


# ==============================================================================
# OPTIONS DE FILTRAGE POUR L'INVENTAIRE
# ==============================================================================

class InventoryFilterOptionsView(APIView):
    """
    Retourne les options de filtrage disponibles pour l'inventaire.

    Endpoint: GET /api/inventory/filter-options/

    Query params optionnels:
    - type: filtrer les options selon un type d'objet spécifique

    Returns:
        {
            "sites": [{"id": 1, "name": "Site A"}, ...],
            "zones": ["Zone 1", "Zone 2", ...],
            "families": ["Palmaceae", "Rosaceae", ...],
            "materials": ["PVC", "Acier", ...],
            "equipment_types": ["Centrifuge", "Submersible", ...],
            "sizes": ["Petit", "Moyen", "Grand"],
            "states": ["bon", "moyen", "mauvais", "critique"],
            "ranges": {
                "surface": [0, 10000],
                "diameter": [0, 500],
                "depth": [0, 100],
                "density": [0, 100]
            }
        }
    """

    def get(self, request):
        from django.db.models import Min, Max

        type_filter = request.query_params.get('type', None)

        # ==============================================================================
        # SITES
        # ==============================================================================
        sites = Site.objects.filter(actif=True).values('id', 'nom_site').order_by('nom_site')
        sites_list = [{'id': s['id'], 'name': s['nom_site']} for s in sites]

        # ==============================================================================
        # ZONES (Sous-sites)
        # ==============================================================================
        zones = list(SousSite.objects.values_list('nom', flat=True).distinct().order_by('nom'))

        # ==============================================================================
        # FAMILLES (végétaux uniquement)
        # ==============================================================================
        families = set()
        if not type_filter or type_filter.lower() in ['arbre', 'arbres']:
            families.update(Arbre.objects.exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['gazon', 'gazons']:
            families.update(Gazon.objects.exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['palmier', 'palmiers']:
            families.update(Palmier.objects.exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['arbuste', 'arbustes']:
            families.update(Arbuste.objects.exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['vivace', 'vivaces']:
            families.update(Vivace.objects.exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['cactus']:
            families.update(Cactus.objects.exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['graminee', 'graminees']:
            families.update(Graminee.objects.exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())

        families_list = sorted(list(families))

        # ==============================================================================
        # MATÉRIAUX (hydraulique uniquement)
        # ==============================================================================
        materials = set()
        if not type_filter or type_filter.lower() in ['vanne', 'vannes']:
            materials.update(Vanne.objects.exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['clapet', 'clapets']:
            materials.update(Clapet.objects.exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['canalisation', 'canalisations']:
            materials.update(Canalisation.objects.exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['aspersion', 'aspersions']:
            materials.update(Aspersion.objects.exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['goutte', 'gouttes']:
            materials.update(Goutte.objects.exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['ballon', 'ballons']:
            materials.update(Ballon.objects.exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())

        materials_list = sorted(list(materials))

        # ==============================================================================
        # TYPES D'ÉQUIPEMENT
        # ==============================================================================
        equipment_types = set()
        if not type_filter or type_filter.lower() in ['pompe', 'pompes']:
            equipment_types.update(Pompe.objects.exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['vanne', 'vannes']:
            equipment_types.update(Vanne.objects.exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['clapet', 'clapets']:
            equipment_types.update(Clapet.objects.exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['canalisation', 'canalisations']:
            equipment_types.update(Canalisation.objects.exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['aspersion', 'aspersions']:
            equipment_types.update(Aspersion.objects.exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['goutte', 'gouttes']:
            equipment_types.update(Goutte.objects.exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())

        equipment_types_list = sorted(list(equipment_types))

        # ==============================================================================
        # TAILLES (statiques basées sur TAILLE_CHOICES)
        # ==============================================================================
        sizes = ['Petit', 'Moyen', 'Grand']

        # ==============================================================================
        # ÉTATS (statiques - à implémenter dans le modèle plus tard)
        # ==============================================================================
        states = ['bon', 'moyen', 'mauvais', 'critique']

        # ==============================================================================
        # PLAGES DE VALEURS
        # ==============================================================================
        ranges = {}

        # Surface (gazons)
        surface_range = Gazon.objects.aggregate(min_val=Min('area_sqm'), max_val=Max('area_sqm'))
        if surface_range['min_val'] is not None:
            ranges['surface'] = [
                float(surface_range['min_val'] or 0),
                float(surface_range['max_val'] or 10000)
            ]

        # Diamètre (puits, pompes, vannes, etc.)
        diameter_values = []
        for Model in [Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte]:
            agg = Model.objects.aggregate(min_val=Min('diametre'), max_val=Max('diametre'))
            if agg['min_val'] is not None:
                diameter_values.append(agg['min_val'])
            if agg['max_val'] is not None:
                diameter_values.append(agg['max_val'])
        if diameter_values:
            ranges['diameter'] = [float(min(diameter_values)), float(max(diameter_values))]

        # Profondeur (puits)
        depth_range = Puit.objects.aggregate(min_val=Min('profondeur'), max_val=Max('profondeur'))
        if depth_range['min_val'] is not None:
            ranges['depth'] = [
                float(depth_range['min_val'] or 0),
                float(depth_range['max_val'] or 100)
            ]

        # Densité (arbustes, vivaces, cactus, graminées)
        density_values = []
        for Model in [Arbuste, Vivace, Cactus, Graminee]:
            agg = Model.objects.aggregate(min_val=Min('densite'), max_val=Max('densite'))
            if agg['min_val'] is not None:
                density_values.append(agg['min_val'])
            if agg['max_val'] is not None:
                density_values.append(agg['max_val'])
        if density_values:
            ranges['density'] = [float(min(density_values)), float(max(density_values))]

        return Response({
            'sites': sites_list,
            'zones': zones,
            'families': families_list,
            'materials': materials_list,
            'equipment_types': equipment_types_list,
            'sizes': sizes,
            'states': states,
            'ranges': ranges
        })


# ==============================================================================
# IMPORT/EXPORT GEO SERVICES
# ==============================================================================

from rest_framework.parsers import MultiPartParser, FormParser
from django.http import HttpResponse
from .services.geo_io import (
    parse_geojson, parse_kml, parse_shapefile,
    convert_geometry, validate_geometry_for_type,
    export_to_geojson, export_to_kml, export_to_shapefile,
    apply_attribute_mapping, suggest_attribute_mapping,
    GEOMETRY_TYPE_MAPPING, OBJECT_FIELDS
)


class GeoImportPreviewView(APIView):
    """
    Preview imported geo data before validation.

    POST /api/import/preview/
    Content-Type: multipart/form-data

    Body:
        - file: The geo file (GeoJSON, KML, KMZ, or ZIP with Shapefile)
        - format: 'geojson' | 'kml' | 'shapefile' (auto-detected if not provided)

    Returns:
        {
            "features": [
                {
                    "index": 0,
                    "geometry": {...},
                    "geometry_type": "Point",
                    "properties": {...},
                    "compatible_types": ["Arbre", "Palmier", "Puit", ...]
                },
                ...
            ],
            "detected_types": {"Point": 10, "Polygon": 5},
            "attributes": ["name", "description", "type", ...],
            "suggested_mapping": {...},
            "errors": []
        }
    """
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file provided'}, status=400)

        file_format = request.data.get('format', '').lower()

        # Auto-detect format from filename
        filename = file_obj.name.lower()
        if not file_format or file_format == 'auto':
            if filename.endswith('.geojson') or filename.endswith('.json'):
                file_format = 'geojson'
            elif filename.endswith('.kml') or filename.endswith('.kmz'):
                file_format = 'kml'
            elif filename.endswith('.zip'):
                file_format = 'shapefile'
            else:
                return Response({'error': 'Could not detect file format. Please specify format parameter.'}, status=400)

        # Read file content
        file_content = file_obj.read()

        # Parse based on format
        if file_format == 'geojson':
            result = parse_geojson(file_content)
        elif file_format == 'kml':
            result = parse_kml(file_content)
        elif file_format == 'shapefile':
            result = parse_shapefile(file_content)
        else:
            return Response({'error': f'Unsupported format: {file_format}'}, status=400)

        # Transform response to match frontend expectations
        detected_types = result.get('detected_types', {})
        attributes = result.get('attributes', [])
        features = result.get('features', [])

        # Add suggested mapping if we have features
        suggested_mapping = {}
        if features and attributes:
            if detected_types:
                most_common_geom = max(detected_types.keys(), key=lambda k: detected_types[k])
                compatible = features[0].get('compatible_types', [])
                if compatible:
                    suggested_mapping = suggest_attribute_mapping(
                        attributes,
                        compatible[0]
                    )

        # Build response matching frontend ImportPreviewResponse interface
        response_data = {
            'format': file_format,
            'feature_count': len(features),
            'geometry_types': list(detected_types.keys()),
            'sample_properties': attributes,
            'features': features,
            'suggested_mapping': suggested_mapping,
            'errors': result.get('errors', []),
        }

        return Response(response_data)


class GeoImportValidateView(APIView):
    """
    Validate imported features before execution.

    POST /api/import/validate/

    Body:
        {
            "features": [...],  // From preview response
            "mapping": {        // Attribute mapping
                "source_attr": "target_field",
                ...
            },
            "target_type": "Arbre",  // Target object type
            "site_id": 1             // Target site ID
        }

    Returns:
        {
            "valid": true|false,
            "valid_count": 10,
            "errors": [
                {"index": 0, "error": "..."},
                ...
            ],
            "warnings": [
                {"index": 1, "warning": "Duplicate detected at ..."},
                ...
            ]
        }
    """

    def post(self, request):
        features = request.data.get('features', [])
        mapping = request.data.get('mapping', {})
        target_type = request.data.get('target_type')
        site_id = request.data.get('site_id')
        auto_detect_site = request.data.get('auto_detect_site', False)

        if not features:
            return Response({'error': 'No features provided'}, status=400)

        if not target_type:
            return Response({'error': 'target_type is required'}, status=400)

        if target_type not in GEOMETRY_TYPE_MAPPING:
            return Response({'error': f'Invalid target_type: {target_type}'}, status=400)

        # Site is not required for Site objects
        site = None
        all_sites = None  # For auto-detect mode
        if target_type != 'Site':
            if auto_detect_site:
                # Load all active sites for geometry-based detection
                all_sites = list(Site.objects.filter(actif=True))
                if not all_sites:
                    return Response({'error': 'No active sites found for auto-detection'}, status=400)
            elif not site_id:
                return Response({'error': 'site_id is required (or enable auto_detect_site)'}, status=400)
            else:
                # Verify site exists
                try:
                    site = Site.objects.get(pk=site_id)
                except Site.DoesNotExist:
                    return Response({'error': f'Site {site_id} not found'}, status=400)

        errors = []
        warnings = []
        valid_count = 0
        invalid_count = 0
        validated_features = []

        expected_geom_type = GEOMETRY_TYPE_MAPPING[target_type]

        for feature in features:
            idx = feature.get('index', 0)
            geometry = feature.get('geometry')
            properties = feature.get('properties', {})
            is_valid = True

            if not geometry:
                errors.append({'index': idx, 'message': 'Missing geometry', 'code': 'MISSING_GEOMETRY'})
                is_valid = False
                invalid_count += 1
                validated_features.append({
                    'index': idx,
                    'is_valid': False,
                    'geometry_type': 'Unknown',
                    'mapped_properties': {}
                })
                continue

            geom_type = geometry.get('type', 'Unknown')

            # Validate geometry type
            geom_valid, error_msg = validate_geometry_for_type(
                GEOSGeometry(json.dumps(geometry), srid=4326),
                target_type
            )

            if not geom_valid:
                errors.append({'index': idx, 'message': error_msg, 'code': 'INVALID_GEOMETRY'})
                is_valid = False
                invalid_count += 1
                validated_features.append({
                    'index': idx,
                    'is_valid': False,
                    'geometry_type': geom_type,
                    'mapped_properties': {}
                })
                continue

            # Check if geometry is within site boundary (only for non-Site objects)
            try:
                geom = convert_geometry(geometry, expected_geom_type)
                detected_site = site  # Use provided site by default

                if auto_detect_site and all_sites:
                    # Auto-detect: find the site that contains this geometry
                    detected_site = None
                    for candidate_site in all_sites:
                        if candidate_site.geometrie_emprise:
                            if candidate_site.geometrie_emprise.contains(geom) or candidate_site.geometrie_emprise.intersects(geom):
                                detected_site = candidate_site
                                break

                    if not detected_site:
                        errors.append({
                            'index': idx,
                            'message': 'Geometry is not within any site boundary',
                            'code': 'NO_SITE_FOUND'
                        })
                        is_valid = False
                        invalid_count += 1
                        validated_features.append({
                            'index': idx,
                            'is_valid': False,
                            'geometry_type': geom_type,
                            'mapped_properties': {},
                            'detected_site_id': None
                        })
                        continue

                elif detected_site and detected_site.geometrie_emprise:
                    # Manual mode: check if geometry is within selected site
                    if not detected_site.geometrie_emprise.contains(geom) and not detected_site.geometrie_emprise.intersects(geom):
                        warnings.append({
                            'index': idx,
                            'message': 'Geometry is outside site boundary',
                            'code': 'OUTSIDE_BOUNDARY'
                        })
            except Exception as e:
                errors.append({'index': idx, 'message': f'Geometry conversion error: {str(e)}', 'code': 'CONVERSION_ERROR'})
                is_valid = False
                invalid_count += 1
                validated_features.append({
                    'index': idx,
                    'is_valid': False,
                    'geometry_type': geom_type,
                    'mapped_properties': {}
                })
                continue

            # Check for duplicates (same location within tolerance)
            try:
                from django.contrib.gis.db.models.functions import Distance
                from django.contrib.gis.measure import D

                # Get model class
                model_class = self._get_model_class(target_type)
                if model_class:
                    if target_type == 'Site':
                        # For Sites, check by geometry overlap
                        nearby = model_class.objects.filter(
                            geometrie_emprise__intersects=geom
                        ).exists()
                    else:
                        # Use detected_site for duplicate check
                        check_site = detected_site if auto_detect_site else site
                        if check_site:
                            nearby = model_class.objects.filter(
                                site=check_site,
                                geometry__distance_lte=(geom, D(m=1))
                            ).exists()
                        else:
                            nearby = False
                    if nearby:
                        warnings.append({
                            'index': idx,
                            'message': 'Possible duplicate: object exists within 1m' if target_type != 'Site' else 'Possible duplicate: site with overlapping geometry exists',
                            'code': 'DUPLICATE'
                        })
            except Exception:
                pass  # Skip duplicate check on error

            # Apply mapping to get mapped properties preview
            mapped_props = apply_attribute_mapping(feature, mapping, target_type)

            valid_count += 1
            feature_result = {
                'index': idx,
                'is_valid': True,
                'geometry_type': geom_type,
                'mapped_properties': mapped_props
            }

            # Include detected site info if in auto-detect mode
            if auto_detect_site and detected_site:
                feature_result['detected_site_id'] = detected_site.pk
                feature_result['detected_site_name'] = detected_site.nom_site

            validated_features.append(feature_result)

        return Response({
            'valid_count': valid_count,
            'invalid_count': invalid_count,
            'errors': errors,
            'warnings': warnings,
            'features': validated_features
        })

    def _get_model_class(self, target_type):
        """Get Django model class from type name."""
        model_mapping = {
            'Site': Site,
            'Arbre': Arbre,
            'Gazon': Gazon,
            'Palmier': Palmier,
            'Arbuste': Arbuste,
            'Vivace': Vivace,
            'Cactus': Cactus,
            'Graminee': Graminee,
            'Puit': Puit,
            'Pompe': Pompe,
            'Vanne': Vanne,
            'Clapet': Clapet,
            'Ballon': Ballon,
            'Canalisation': Canalisation,
            'Aspersion': Aspersion,
            'Goutte': Goutte,
        }
        return model_mapping.get(target_type)


class GeoImportExecuteView(APIView):
    """
    Execute the import and create objects in database.

    POST /api/import/execute/

    Body:
        {
            "features": [...],
            "mapping": {...},
            "target_type": "Arbre",
            "site_id": 1,
            "sous_site_id": null  // Optional
        }

    Returns:
        {
            "created": [1, 2, 3, ...],  // IDs of created objects
            "errors": [
                {"index": 0, "error": "..."},
                ...
            ],
            "summary": {
                "total": 10,
                "created": 8,
                "failed": 2
            }
        }
    """

    def post(self, request):
        features = request.data.get('features', [])
        mapping = request.data.get('mapping', {})
        target_type = request.data.get('target_type')
        site_id = request.data.get('site_id')
        sous_site_id = request.data.get('sous_site_id')
        auto_detect_site = request.data.get('auto_detect_site', False)

        if not features:
            return Response({'error': 'No features provided'}, status=400)

        if not target_type or target_type not in GEOMETRY_TYPE_MAPPING:
            return Response({'error': 'Invalid target_type'}, status=400)

        # Site is not required for Site objects
        site = None
        sous_site = None
        all_sites = None  # For auto-detect mode
        if target_type != 'Site':
            if auto_detect_site:
                # Load all active sites for geometry-based detection
                all_sites = list(Site.objects.filter(actif=True))
                if not all_sites:
                    return Response({'error': 'No active sites found for auto-detection'}, status=400)
            elif not site_id:
                return Response({'error': 'site_id is required (or enable auto_detect_site)'}, status=400)
            else:
                # Get site and optionally sous_site
                try:
                    site = Site.objects.get(pk=site_id)
                except Site.DoesNotExist:
                    return Response({'error': f'Site {site_id} not found'}, status=400)

            if sous_site_id:
                try:
                    sous_site = SousSite.objects.get(pk=sous_site_id)
                except SousSite.DoesNotExist:
                    return Response({'error': f'SousSite {sous_site_id} not found'}, status=400)

        # Get model class
        model_class = self._get_model_class(target_type)
        if not model_class:
            return Response({'error': f'Unknown model for type: {target_type}'}, status=400)

        expected_geom_type = GEOMETRY_TYPE_MAPPING[target_type]

        created_ids = []
        errors = []

        for feature in features:
            idx = feature.get('index', 0)

            try:
                geometry = feature.get('geometry')
                if not geometry:
                    errors.append({'index': idx, 'error': 'Missing geometry'})
                    continue

                # Convert geometry
                geom = convert_geometry(geometry, expected_geom_type)

                # Apply attribute mapping
                attributes = apply_attribute_mapping(feature, mapping, target_type)

                # Handle Site objects differently
                if target_type == 'Site':
                    # Sites have different field names
                    attributes['geometrie_emprise'] = geom
                    attributes['centroid'] = geom.centroid
                    attributes['actif'] = True
                    # Set default name if not provided
                    if 'nom_site' not in attributes:
                        props = feature.get('properties', {})
                        attributes['nom_site'] = props.get('name') or props.get('nom') or f"Site Import {idx + 1}"
                    # Set default code if not provided
                    if 'code_site' not in attributes:
                        import uuid
                        attributes['code_site'] = f"SITE_{uuid.uuid4().hex[:8].upper()}"
                else:
                    # Add required fields for other objects
                    # Determine the site for this feature
                    target_site = site  # Use provided site by default

                    if auto_detect_site and all_sites:
                        # Auto-detect: find the site that contains this geometry
                        target_site = None
                        for candidate_site in all_sites:
                            if candidate_site.geometrie_emprise:
                                if candidate_site.geometrie_emprise.contains(geom) or candidate_site.geometrie_emprise.intersects(geom):
                                    target_site = candidate_site
                                    break

                        if not target_site:
                            errors.append({'index': idx, 'error': 'Geometry is not within any site boundary'})
                            continue

                    attributes['site'] = target_site
                    if sous_site:
                        attributes['sous_site'] = sous_site
                    attributes['geometry'] = geom

                    # Set default name if not provided
                    if 'nom' not in attributes and 'nom' in OBJECT_FIELDS.get(target_type, []):
                        attributes['nom'] = f"{target_type} Import {idx + 1}"

                # Create object
                obj = model_class.objects.create(**attributes)
                created_ids.append(obj.pk)

            except Exception as e:
                errors.append({'index': idx, 'error': str(e)})

        return Response({
            'created': created_ids,
            'errors': errors,
            'summary': {
                'total': len(features),
                'created': len(created_ids),
                'failed': len(errors)
            }
        })

    def _get_model_class(self, target_type):
        """Get Django model class from type name."""
        model_mapping = {
            'Site': Site,
            'Arbre': Arbre,
            'Gazon': Gazon,
            'Palmier': Palmier,
            'Arbuste': Arbuste,
            'Vivace': Vivace,
            'Cactus': Cactus,
            'Graminee': Graminee,
            'Puit': Puit,
            'Pompe': Pompe,
            'Vanne': Vanne,
            'Clapet': Clapet,
            'Ballon': Ballon,
            'Canalisation': Canalisation,
            'Aspersion': Aspersion,
            'Goutte': Goutte,
        }
        return model_mapping.get(target_type)


# ==============================================================================
# VUES POUR LES OPÉRATIONS GÉOMÉTRIQUES
# ==============================================================================

from .services.validation import (
    validate_geometry,
    detect_duplicates,
    check_within_site,
    simplify_geometry,
    split_polygon,
    merge_polygons,
    calculate_geometry_metrics,
    buffer_geometry,
)


class GeometrySimplifyView(APIView):
    """
    POST /api/geometry/simplify/
    Simplifie une géométrie en réduisant le nombre de sommets.

    Request body:
    {
        "geometry": { GeoJSON geometry },
        "tolerance": 0.0001,  // Optional, default 0.0001 degrees (~11m)
        "preserve_topology": true  // Optional, default true
    }

    Response:
    {
        "geometry": { simplified GeoJSON geometry },
        "stats": {
            "original_coords": 150,
            "simplified_coords": 45,
            "reduction_percent": 70.0,
            ...
        }
    }
    """

    def post(self, request):
        geometry_data = request.data.get('geometry')
        tolerance = request.data.get('tolerance', 0.0001)
        preserve_topology = request.data.get('preserve_topology', True)

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)

        try:
            # Convert GeoJSON to GEOS geometry
            geom = GEOSGeometry(json.dumps(geometry_data))

            # Simplify
            simplified, stats = simplify_geometry(
                geom,
                tolerance=tolerance,
                preserve_topology=preserve_topology
            )

            # Convert back to GeoJSON
            simplified_geojson = json.loads(simplified.geojson)

            return Response({
                'geometry': simplified_geojson,
                'stats': stats
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometrySplitView(APIView):
    """
    POST /api/geometry/split/
    Divise un polygone avec une ligne de coupe.

    Request body:
    {
        "polygon": { GeoJSON Polygon },
        "split_line": { GeoJSON LineString }
    }

    Response:
    {
        "geometries": [ { GeoJSON Polygon }, ... ],
        "stats": {
            "success": true,
            "num_parts": 2,
            "areas": [0.001, 0.002]
        }
    }
    """

    def post(self, request):
        polygon_data = request.data.get('polygon')
        split_line_data = request.data.get('split_line')

        if not polygon_data:
            return Response({'error': 'polygon is required'}, status=400)
        if not split_line_data:
            return Response({'error': 'split_line is required'}, status=400)

        try:
            polygon = GEOSGeometry(json.dumps(polygon_data))
            split_line = GEOSGeometry(json.dumps(split_line_data))

            if polygon.geom_type not in ('Polygon', 'MultiPolygon'):
                return Response({'error': 'First geometry must be a Polygon'}, status=400)
            if split_line.geom_type != 'LineString':
                return Response({'error': 'Split line must be a LineString'}, status=400)

            result_polygons, stats = split_polygon(polygon, split_line)

            # Convert to GeoJSON
            geometries = [json.loads(p.geojson) for p in result_polygons]

            return Response({
                'geometries': geometries,
                'stats': stats
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometryMergeView(APIView):
    """
    POST /api/geometry/merge/
    Fusionne plusieurs polygones en un seul.

    Request body:
    {
        "polygons": [ { GeoJSON Polygon }, { GeoJSON Polygon }, ... ]
    }

    Response:
    {
        "geometry": { GeoJSON Polygon or MultiPolygon },
        "stats": {
            "success": true,
            "input_count": 3,
            "output_type": "Polygon",
            ...
        }
    }
    """

    def post(self, request):
        polygons_data = request.data.get('polygons', [])

        if not polygons_data or len(polygons_data) < 2:
            return Response({'error': 'At least 2 polygons are required'}, status=400)

        try:
            polygons = []
            for i, poly_data in enumerate(polygons_data):
                poly = GEOSGeometry(json.dumps(poly_data))
                if poly.geom_type not in ('Polygon', 'MultiPolygon'):
                    return Response({
                        'error': f'Geometry at index {i} must be a Polygon'
                    }, status=400)
                polygons.append(poly)

            result, stats = merge_polygons(polygons)

            if result is None:
                return Response({
                    'geometry': None,
                    'stats': stats
                }, status=400)

            return Response({
                'geometry': json.loads(result.geojson),
                'stats': stats
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometryValidateView(APIView):
    """
    POST /api/geometry/validate/
    Valide une géométrie et détecte les doublons potentiels.

    Request body:
    {
        "geometry": { GeoJSON geometry },
        "target_type": "Arbre",  // Optional, for duplicate detection
        "site_id": 1,  // Optional, for duplicate detection and boundary check
        "check_duplicates": true,  // Optional
        "check_within_site": true,  // Optional
        "duplicate_tolerance": 0.0001  // Optional, degrees
    }

    Response:
    {
        "validation": {
            "is_valid": true,
            "errors": [],
            "warnings": []
        },
        "duplicates": [...],  // If check_duplicates=true
        "within_site": {...}  // If check_within_site=true
    }
    """

    def post(self, request):
        geometry_data = request.data.get('geometry')
        target_type = request.data.get('target_type')
        site_id = request.data.get('site_id')
        check_dup = request.data.get('check_duplicates', False)
        check_site = request.data.get('check_within_site', False)
        dup_tolerance = request.data.get('duplicate_tolerance', 0.0001)

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)

        try:
            geom = GEOSGeometry(json.dumps(geometry_data))

            response_data = {}

            # Basic validation
            response_data['validation'] = validate_geometry(geom)

            # Duplicate detection
            if check_dup and target_type:
                model_class = self._get_model_class(target_type)
                if model_class:
                    response_data['duplicates'] = detect_duplicates(
                        geom,
                        model_class,
                        site_id=site_id,
                        tolerance=dup_tolerance
                    )
                else:
                    response_data['duplicates'] = []
                    response_data['validation']['warnings'].append({
                        'code': 'UNKNOWN_TYPE',
                        'message': f'Unknown target type: {target_type}'
                    })

            # Within site check
            if check_site and site_id:
                response_data['within_site'] = check_within_site(geom, site_id)

            return Response(response_data)

        except Exception as e:
            return Response({'error': str(e)}, status=400)

    def _get_model_class(self, target_type):
        """Get Django model class from type name."""
        model_mapping = {
            'Site': Site,
            'Arbre': Arbre,
            'Gazon': Gazon,
            'Palmier': Palmier,
            'Arbuste': Arbuste,
            'Vivace': Vivace,
            'Cactus': Cactus,
            'Graminee': Graminee,
            'Puit': Puit,
            'Pompe': Pompe,
            'Vanne': Vanne,
            'Clapet': Clapet,
            'Ballon': Ballon,
            'Canalisation': Canalisation,
            'Aspersion': Aspersion,
            'Goutte': Goutte,
        }
        return model_mapping.get(target_type)


class GeometryCalculateView(APIView):
    """
    POST /api/geometry/calculate/
    Calcule les métriques d'une géométrie (aire, longueur, périmètre, etc.).

    Request body:
    {
        "geometry": { GeoJSON geometry }
    }

    Response:
    {
        "metrics": {
            "geometry_type": "Polygon",
            "area_m2": 1234.56,
            "area_hectares": 0.1234,
            "perimeter_m": 456.78,
            "centroid": { "lng": -7.5, "lat": 33.5 },
            "bbox": { "min_lng": ..., ... }
        }
    }
    """

    def post(self, request):
        geometry_data = request.data.get('geometry')

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)

        try:
            geom = GEOSGeometry(json.dumps(geometry_data))
            metrics = calculate_geometry_metrics(geom)

            return Response({'metrics': metrics})

        except Exception as e:
            return Response({'error': str(e)}, status=400)


class GeometryBufferView(APIView):
    """
    POST /api/geometry/buffer/
    Crée un buffer (zone tampon) autour d'une géométrie.

    Request body:
    {
        "geometry": { GeoJSON geometry },
        "distance": 10,  // Distance in meters
        "quad_segs": 8  // Optional, segments for curves (default 8)
    }

    Response:
    {
        "geometry": { GeoJSON Polygon },
        "stats": {
            "input_type": "Point",
            "output_type": "Polygon",
            "distance_meters": 10
        }
    }
    """

    def post(self, request):
        geometry_data = request.data.get('geometry')
        distance = request.data.get('distance')
        quad_segs = request.data.get('quad_segs', 8)

        if not geometry_data:
            return Response({'error': 'geometry is required'}, status=400)
        if distance is None:
            return Response({'error': 'distance (in meters) is required'}, status=400)

        try:
            geom = GEOSGeometry(json.dumps(geometry_data))
            buffered, stats = buffer_geometry(geom, distance, quad_segs)

            return Response({
                'geometry': json.loads(buffered.geojson),
                'stats': stats
            })

        except Exception as e:
            return Response({'error': str(e)}, status=400)
