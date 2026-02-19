# api/views_inventory.py
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Q, Count, Min, Max
from django.contrib.gis.geos import GEOSGeometry
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

        # Filtrer par rôle (ADMIN, CLIENT, SUPERVISEUR)
        user = request.user
        structure_filter = None
        superviseur_filter = None
        if user.is_authenticated:
            roles = list(user.roles_utilisateur.values_list('role__nom_role', flat=True))

            # ADMIN voit tout - pas de filtre
            if 'ADMIN' in roles:
                pass
            # CLIENT voit uniquement les sites de sa structure
            elif 'CLIENT' in roles and hasattr(user, 'client_profile'):
                structure_filter = user.client_profile.structure
            # SUPERVISEUR voit uniquement les sites qui lui sont affectés
            elif 'SUPERVISEUR' in roles:
                if hasattr(user, 'superviseur_profile'):
                    superviseur_filter = user.superviseur_profile
                else:
                    # Superviseur sans profil = aucun objet visible
                    return Response({
                        'count': 0,
                        'next': None,
                        'previous': None,
                        'results': []
                    })

        # Collecter les résultats de chaque type
        all_results = []

        for type_name in target_types:
            if type_name not in MODEL_MAP:
                continue

            model_class, serializer_class = MODEL_MAP[type_name]

            # Construire le queryset avec select_related pour éviter les N+1
            qs = model_class.objects.select_related('site', 'sous_site')

            # Appliquer les filtres de rôle
            if structure_filter:
                qs = qs.filter(site__structure_client=structure_filter)
            elif superviseur_filter:
                qs = qs.filter(site__superviseur=superviseur_filter)

            if site_filter:
                qs = qs.filter(site_id=site_filter)

            if etat_filter:
                qs = qs.filter(etat=etat_filter)

            # Filtre famille (pour les types qui ont ce champ)
            if famille_filter and hasattr(model_class, 'famille'):
                qs = qs.filter(famille__icontains=famille_filter)

            # Filtre recherche
            if search_query:
                # Retirer le nom du type de la requête de recherche.
                # Le frontend affiche "Vanne 3962" comme nom pour les objets
                # sans champ 'nom', mais "Vanne" n'est pas stocké en base —
                # c'est le object_type injecté à la sérialisation.
                # On extrait les tokens utiles en retirant le nom du type.
                type_aliases = {
                    'graminee': ['graminée', 'graminee'],
                    'puit': ['puits', 'puit'],
                }
                type_names_to_strip = {type_name.lower(), type_name.capitalize().lower()}
                for alias in type_aliases.get(type_name, []):
                    type_names_to_strip.add(alias.lower())

                # Retirer les tokens qui correspondent au nom du type
                tokens = search_query.split()
                filtered_tokens = [t for t in tokens if t.lower() not in type_names_to_strip]
                effective_query = ' '.join(filtered_tokens).strip()

                # Si après retrait du nom de type il ne reste rien,
                # la recherche visait uniquement le type → pas de filtre supplémentaire
                if effective_query:
                    q = Q(site__nom_site__icontains=effective_query) | Q(site__code_site__icontains=effective_query)
                    if hasattr(model_class, 'nom'):
                        q |= Q(nom__icontains=effective_query)
                    if hasattr(model_class, 'famille'):
                        q |= Q(famille__icontains=effective_query)
                    if hasattr(model_class, 'marque'):
                        q |= Q(marque__icontains=effective_query)
                    if hasattr(model_class, 'type'):
                        q |= Q(type__icontains=effective_query)
                    if hasattr(model_class, 'observation'):
                        q |= Q(observation__icontains=effective_query)
                    if hasattr(model_class, 'sous_site'):
                        q |= Q(sous_site__nom__icontains=effective_query)
                    # Recherche par ID si la query restante est numérique
                    if effective_query.isdigit():
                        q |= Q(id=int(effective_query))
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
# ENDPOINT UNIFIÉ POUR LA CARTE (avec Bounding Box)
# ==============================================================================

class MapObjectsView(APIView):
    """
    Endpoint unique et intelligent pour charger tous les objets de la carte.

    Permissions automatiques basées sur le rôle:
    - ADMIN: voit tout
    - CLIENT: voit uniquement ses sites et objets
    - SUPERVISEUR: voit uniquement les sites/objets liés aux tâches de ses équipes

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
        structure_filter = None
        superviseur_filter = None  # (site_ids, object_ids)

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            if 'ADMIN' in roles:
                is_admin = True
            elif 'CLIENT' in roles and hasattr(user, 'client_profile'):
                structure_filter = user.client_profile.structure
            elif 'SUPERVISEUR' in roles:
                superviseur_filter = self._get_superviseur_filters(user)

        # ==============================================================================
        # 1. CHARGER LES SITES (toujours tous car peu nombreux)
        # ==============================================================================
        if not requested_types or 'sites' in requested_types:
            sites = Site.objects.filter(actif=True).order_by('id')

            # Appliquer les filtres de permissions
            if not is_admin:
                if structure_filter:
                    sites = sites.filter(structure_client=structure_filter)
                elif superviseur_filter:
                    site_ids, _ = superviseur_filter
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
                            if structure_filter:
                                queryset = queryset.filter(site__structure_client=structure_filter)
                            elif superviseur_filter:
                                _, object_ids = superviseur_filter
                                # SUPERVISEUR: ne voir QUE les objets directement liés aux tâches
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

    def _get_superviseur_filters(self, user):
        """
        Récupère les IDs des sites et objets affectés directement au superviseur.
        Returns: tuple (site_ids, object_ids)

        Le superviseur voit:
        - Les sites qui lui sont affectés directement (via site.superviseur)
        - Tous les objets de ces sites

        NOUVEAU SYSTÈME: Affectation directe superviseur → sites (plus simple et plus clair)
        """
        try:
            superviseur = user.superviseur_profile

            # Sites affectés directement au superviseur
            site_ids = list(
                Site.objects.filter(superviseur=superviseur).values_list('id', flat=True)
            )

            if not site_ids:
                return ([], [])

            # Tous les objets GIS de ces sites
            object_ids = list(
                Objet.objects.filter(site_id__in=site_ids).values_list('id', flat=True)
            )

            return (site_ids, object_ids)
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
        type_filter = request.query_params.get('type', None)

        # Obtenir les querysets filtrés selon les permissions de l'utilisateur
        user = request.user
        site_filter = Q()  # Par défaut, pas de filtre (ADMIN)

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            if 'ADMIN' not in roles:
                if 'CLIENT' in roles and hasattr(user, 'client_profile'):
                    # CLIENT: uniquement les sites de sa structure
                    structure = user.client_profile.structure
                    if structure:
                        site_filter = Q(structure_client=structure)
                        object_filter = Q(site__structure_client=structure)
                    else:
                        site_filter = Q(pk__in=[])
                        object_filter = Q(pk__in=[])
                elif 'SUPERVISEUR' in roles and hasattr(user, 'superviseur_profile'):
                    # SUPERVISEUR: uniquement les sites qui lui sont affectés
                    site_filter = Q(superviseur=user.superviseur_profile)
                    object_filter = Q(site__superviseur=user.superviseur_profile)
                else:
                    # Aucun accès
                    site_filter = Q(pk__in=[])
                    object_filter = Q(pk__in=[])
            else:
                # ADMIN: pas de filtre
                object_filter = Q()
        else:
            # Non authentifié: aucun accès
            site_filter = Q(pk__in=[])
            object_filter = Q(pk__in=[])

        # ==============================================================================
        # SITES
        # ==============================================================================
        sites = Site.objects.filter(site_filter).filter(actif=True).values('id', 'nom_site').order_by('nom_site')
        sites_list = [{'id': s['id'], 'name': s['nom_site']} for s in sites]

        # ==============================================================================
        # ZONES (Sous-sites)
        # ==============================================================================
        zones = list(SousSite.objects.filter(object_filter).values_list('nom', flat=True).distinct().order_by('nom'))

        # ==============================================================================
        # FAMILLES (végétaux uniquement)
        # ==============================================================================
        families = set()
        if not type_filter or type_filter.lower() in ['arbre', 'arbres']:
            families.update(Arbre.objects.filter(object_filter).exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['gazon', 'gazons']:
            families.update(Gazon.objects.filter(object_filter).exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['palmier', 'palmiers']:
            families.update(Palmier.objects.filter(object_filter).exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['arbuste', 'arbustes']:
            families.update(Arbuste.objects.filter(object_filter).exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['vivace', 'vivaces']:
            families.update(Vivace.objects.filter(object_filter).exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['cactus']:
            families.update(Cactus.objects.filter(object_filter).exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['graminee', 'graminees']:
            families.update(Graminee.objects.filter(object_filter).exclude(famille__isnull=True).exclude(famille='').values_list('famille', flat=True).distinct())

        families_list = sorted(list(families))

        # ==============================================================================
        # MATÉRIAUX (hydraulique uniquement)
        # ==============================================================================
        materials = set()
        if not type_filter or type_filter.lower() in ['vanne', 'vannes']:
            materials.update(Vanne.objects.filter(object_filter).exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['clapet', 'clapets']:
            materials.update(Clapet.objects.filter(object_filter).exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['canalisation', 'canalisations']:
            materials.update(Canalisation.objects.filter(object_filter).exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['aspersion', 'aspersions']:
            materials.update(Aspersion.objects.filter(object_filter).exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['goutte', 'gouttes']:
            materials.update(Goutte.objects.filter(object_filter).exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['ballon', 'ballons']:
            materials.update(Ballon.objects.filter(object_filter).exclude(materiau__isnull=True).exclude(materiau='').values_list('materiau', flat=True).distinct())

        materials_list = sorted(list(materials))

        # ==============================================================================
        # TYPES D'ÉQUIPEMENT
        # ==============================================================================
        equipment_types = set()
        if not type_filter or type_filter.lower() in ['pompe', 'pompes']:
            equipment_types.update(Pompe.objects.filter(object_filter).exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['vanne', 'vannes']:
            equipment_types.update(Vanne.objects.filter(object_filter).exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['clapet', 'clapets']:
            equipment_types.update(Clapet.objects.filter(object_filter).exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['canalisation', 'canalisations']:
            equipment_types.update(Canalisation.objects.filter(object_filter).exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['aspersion', 'aspersions']:
            equipment_types.update(Aspersion.objects.filter(object_filter).exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())
        if not type_filter or type_filter.lower() in ['goutte', 'gouttes']:
            equipment_types.update(Goutte.objects.filter(object_filter).exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct())

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
        surface_range = Gazon.objects.filter(object_filter).aggregate(min_val=Min('area_sqm'), max_val=Max('area_sqm'))
        if surface_range['min_val'] is not None:
            ranges['surface'] = [
                float(surface_range['min_val'] or 0),
                float(surface_range['max_val'] or 10000)
            ]

        # Diamètre (puits, pompes, vannes, etc.)
        diameter_values = []
        for Model in [Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte]:
            agg = Model.objects.filter(object_filter).aggregate(min_val=Min('diametre'), max_val=Max('diametre'))
            if agg['min_val'] is not None:
                diameter_values.append(agg['min_val'])
            if agg['max_val'] is not None:
                diameter_values.append(agg['max_val'])
        if diameter_values:
            ranges['diameter'] = [float(min(diameter_values)), float(max(diameter_values))]

        # Profondeur (puits)
        depth_range = Puit.objects.filter(object_filter).aggregate(min_val=Min('profondeur'), max_val=Max('profondeur'))
        if depth_range['min_val'] is not None:
            ranges['depth'] = [
                float(depth_range['min_val'] or 0),
                float(depth_range['max_val'] or 100)
            ]

        # Densité (arbustes, vivaces, cactus, graminées)
        density_values = []
        for Model in [Arbuste, Vivace, Cactus, Graminee]:
            agg = Model.objects.filter(object_filter).aggregate(min_val=Min('densite'), max_val=Max('densite'))
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
