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
        from rest_framework.pagination import PageNumberPagination
        from datetime import timedelta
        from django.utils import timezone

        # Récupérer tous les objets avec prefetch des 15 types enfants
        objets = Objet.objects.select_related(
            'arbre', 'gazon', 'palmier', 'arbuste', 'vivace', 'cactus', 'graminee',
            'puit', 'pompe', 'vanne', 'clapet', 'canalisation', 'aspersion', 'goutte', 'ballon',
            'site', 'sous_site'
        ).order_by('id')

        # Appliquer les filtres
        objets = self.apply_id_filter(objets, request)  # ID filter first for performance
        objets = self.apply_type_filter(objets, request)
        objets = self.apply_site_filter(objets, request)
        objets = self.apply_state_filter(objets, request)
        objets = self.apply_search_filter(objets, request)
        objets = self.apply_range_filters(objets, request)
        objets = self.apply_date_filters(objets, request)
        objets = self.apply_specific_filters(objets, request)

        # Optimisation : limiter les champs récupérés avec only()
        # Note: on ne peut pas utiliser only() avec le polymorphisme car on a besoin de tous les champs
        # pour déterminer le type réel. On utilise donc select_related qui est déjà en place.
        
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
        
        # Override page_size if specified in query params
        page_size_param = request.query_params.get('page_size', None)
        if page_size_param:
            try:
                paginator.page_size = int(page_size_param)
            except ValueError:
                pass

        # Paginer les résultats
        page = paginator.paginate_queryset(results, request)

        if page is not None:
            return paginator.get_paginated_response(page)

        return Response({
            'count': len(results),
            'results': results
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
