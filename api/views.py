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
        Filter sites by client if the logged-in user is a CLIENT.
        Admin and other roles see all sites.
        """
        queryset = Site.objects.all().order_by('id')
        user = self.request.user

        if user.is_authenticated:
            # Check if user has CLIENT role
            has_client_role = user.roles_utilisateur.filter(role__nom_role='CLIENT').exists()
            if has_client_role and hasattr(user, 'client_profile'):
                # Filter sites belonging to this client
                queryset = queryset.filter(client=user.client_profile)

        return queryset


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
    Vue pour la recherche multicritère.
    Accepte un paramètre de requête `q`.
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
            
        # Recherche sur les Arbres (par nom)
        arbres = Arbre.objects.filter(nom__icontains=query)
        for item in arbres:
            location = item.geometry
            results.append({
                'id': f"arbre-{item.pk}",
                'name': f"{item.nom}",
                'type': 'Arbre',
                'location': {'type': 'Point', 'coordinates': [location.x, location.y]} if location else None,
            })

        # Limiter le nombre total de résultats
        return Response(results[:20])


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
            'sites': (255, 0, 0),
            'sousSites': (255, 165, 0),
            'arbres': (34, 139, 34),
            'gazons': (144, 238, 144),
            'palmiers': (139, 69, 19),
            'arbustes': (50, 205, 50),
            'vivaces': (147, 112, 219),
            'cactus': (85, 107, 47),
            'graminees': (154, 205, 50),
            'puits': (0, 0, 255),
            'pompes': (0, 128, 255),
            'vannes': (255, 140, 0),
            'clapets': (255, 215, 0),
            'canalisations': (128, 128, 128),
            'aspersions': (0, 255, 255),
            'gouttes': (0, 191, 255),
            'ballons': (70, 130, 180)
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
    """
    def get(self, request, *args, **kwargs):
        from django.db.models import Count, Avg, Sum, Max, Min

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
    - site: filtrer par site ID
    - page: numéro de page (pagination 50 items)

    Returns:
        {
            "count": 450,
            "next": "url_page_suivante",
            "previous": null,
            "results": [
                {
                    "type": "Feature",
                    "id": 1,
                    "geometry": {...},
                    "properties": {
                        "object_type": "Arbre",
                        "nom": "Palmier Phoenix",
                        ...
                    }
                },
                ...
            ]
        }
    """

    def get(self, request):
        from rest_framework.pagination import PageNumberPagination

        # Récupérer tous les objets avec prefetch des 15 types enfants
        # order_by('id') pour éviter UnorderedObjectListWarning lors de la pagination
        objets = Objet.objects.select_related(
            'arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee',
            'puit', 'pompe', 'vanne', 'clapet', 'canalisation', 'aspersion', 'goutte', 'ballon',
            'site', 'sous_site'
        ).order_by('id')

        # Filter by client's sites if user is a CLIENT
        user = request.user
        if user.is_authenticated:
            has_client_role = user.roles_utilisateur.filter(role__nom_role='CLIENT').exists()
            if has_client_role and hasattr(user, 'client_profile'):
                objets = objets.filter(site__client=user.client_profile)

        # Filtrage par type si spécifié
        type_filter = request.query_params.get('type', None)
        if type_filter:
            # Gérer les types multiples séparés par une virgule
            target_types = [t.strip().lower() for t in type_filter.split(',')]
            
            # Filtrer les objets qui ont l'un des attributs demandés
            # Optimisation: Au lieu de itérer, on pourrait utiliser des Q objects si on connaissait les champs à l'avance
            # Mais ici, on reste sur la logique existante pour la compatibilité
            objets_ids = []
            for obj in objets:
                for type_attr in target_types:
                    if hasattr(obj, type_attr):
                        objets_ids.append(obj.id)
                        break
            objets = objets.filter(id__in=objets_ids)

        # Filtrage par site si spécifié
        site_filter = request.query_params.get('site', None)
        if site_filter:
            objets = objets.filter(site_id=site_filter)

        # Filtrage par état si spécifié
        etat_filter = request.query_params.get('etat', None)
        if etat_filter:
            objets = objets.filter(etat=etat_filter)

        # Filtrage par famille si spécifié (un peu plus complexe car dépendant du sous-type)
        famille_filter = request.query_params.get('famille', None)
        if famille_filter:
            # On doit filtrer sur les tables enfants qui ont le champ famille
            # Comme Objet n'a pas de champ famille, on utilise une requête Q ou on itère
             # Optimisation: utiliser les relations inverses
            from django.db.models import Q
            famille_query = Q(arbre__famille__icontains=famille_filter) | \
                            Q(gazon__famille__icontains=famille_filter) | \
                            Q(palmier__famille__icontains=famille_filter) | \
                            Q(arbuste__famille__icontains=famille_filter) | \
                            Q(vivace__famille__icontains=famille_filter) | \
                            Q(cactus__famille__icontains=famille_filter) | \
                            Q(graminee__famille__icontains=famille_filter)
            objets = objets.filter(famille_query)

        # Construire la liste des résultats avec les serializers appropriés
        results = []
        for objet in objets:
            objet_reel = objet.get_type_reel()
            if objet_reel:
                # Récupérer le serializer approprié
                serializer_class = self._get_serializer_class(objet_reel)
                serializer = serializer_class(objet_reel)

                # Ajouter le type d'objet dans les propriétés
                data = serializer.data
                if 'properties' in data:
                    data['properties']['object_type'] = objet.get_nom_type()

                results.append(data)

        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = 50

        # Paginer les résultats
        page = paginator.paginate_queryset(results, request)

        if page is not None:
            return paginator.get_paginated_response(page)

        return Response({
            'count': len(results),
            'results': results
        })

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
# ENDPOINT UNIFIÉ POUR LA CARTE (avec Bounding Box)
# ==============================================================================

class MapObjectsView(APIView):
    """
    Endpoint unique et intelligent pour charger tous les objets de la carte.

    Supporte :
    - Filtrage par bounding box (zone visible)
    - Filtrage par types d'objets
    - Chargement optimisé selon le zoom

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

        # Check if user is a CLIENT to filter by their sites only
        client_filter = None
        user = request.user
        if user.is_authenticated:
            has_client_role = user.roles_utilisateur.filter(role__nom_role='CLIENT').exists()
            if has_client_role and hasattr(user, 'client_profile'):
                client_filter = user.client_profile

        # ==============================================================================
        # 1. CHARGER LES SITES (toujours tous car peu nombreux)
        # ==============================================================================
        if not requested_types or 'sites' in requested_types:
            sites = Site.objects.filter(actif=True).order_by('id')

            # Filter by client if user is a CLIENT
            if client_filter:
                sites = sites.filter(client=client_filter)

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

                # Charger chaque type avec filtrage bbox
                for type_name in types_to_load:
                    if type_name in type_mapping:
                        Model, Serializer = type_mapping[type_name]

                        # Query avec bbox filter
                        queryset = Model.objects.filter(
                            geometry__intersects=bbox_polygon
                        ).select_related('site', 'sous_site')

                        # Filter by client's sites if user is a CLIENT
                        if client_filter:
                            queryset = queryset.filter(site__client=client_filter)

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
