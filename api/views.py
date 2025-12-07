# api/views.py
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q

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
# VUES POUR LA HIÉRARCHIE SPATIALE
# ==============================================================================

class SiteListCreateView(generics.ListCreateAPIView):
    queryset = Site.objects.all().order_by('id')
    serializer_class = SiteSerializer
    filterset_class = SiteFilter


class SiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Site.objects.all()
    serializer_class = SiteSerializer


class SousSiteListCreateView(generics.ListCreateAPIView):
    queryset = SousSite.objects.all().order_by('id')
    serializer_class = SousSiteSerializer
    filterset_class = SousSiteFilter


class SousSiteDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SousSite.objects.all()
    serializer_class = SousSiteSerializer


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
    Vue générique pour exporter les données en CSV ou Excel.
    Paramètres de requête:
    - model: nom du modèle (arbres, gazons, palmiers, etc.)
    - format: csv ou xlsx (défaut: csv)
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
        if export_format not in ['csv', 'xlsx']:
            return Response({'error': 'Format invalide. Utilisez csv ou xlsx.'}, status=400)

        # Appliquer les filtres (réutilise la logique de filtrage)
        queryset = model_class.objects.all()

        # Récupérer tous les objets (pas de pagination pour l'export)
        objects = list(queryset.values())

        if not objects:
            return Response({'error': 'Aucune donnée à exporter'}, status=404)

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

        # Filtrage par type si spécifié
        type_filter = request.query_params.get('type', None)
        if type_filter:
            # Convertir en lowercase pour la recherche hasattr
            type_attr = type_filter.lower()
            # Filtrer les objets qui ont cet attribut
            objets_ids = []
            for obj in objets:
                if hasattr(obj, type_attr):
                    objets_ids.append(obj.id)
            objets = objets.filter(id__in=objets_ids)

        # Filtrage par site si spécifié
        site_filter = request.query_params.get('site', None)
        if site_filter:
            objets = objets.filter(site_id=site_filter)

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

        # ==============================================================================
        # 1. CHARGER LES SITES (toujours tous car peu nombreux)
        # ==============================================================================
        if not requested_types or 'sites' in requested_types:
            sites = Site.objects.filter(actif=True).order_by('id')

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
                        ).select_related('site', 'sous_site').order_by('id')[:100]  # 100 par type max

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
