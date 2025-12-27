from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .models import TypeReclamation, Urgence, Reclamation, HistoriqueReclamation, SatisfactionClient
from api_users.models import Equipe
from django.db import transaction
from .serializers import (
    TypeReclamationSerializer,
    UrgenceSerializer,
    ReclamationListSerializer,
    ReclamationDetailSerializer,
    ReclamationCreateSerializer,
    HistoriqueReclamationSerializer,
    SatisfactionClientSerializer
)
from .permissions import IsReclamationCreatorOrTeamReader

class TypeReclamationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les types de réclamation.
    Lecture seule. Retourne uniquement les actifs.
    """
    queryset = TypeReclamation.objects.filter(actif=True)
    serializer_class = TypeReclamationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [OrderingFilter]
    ordering_fields = ['nom_reclamation', 'categorie']


class UrgenceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet pour les niveaux d'urgence.
    Lecture seule. Ordonné par priorité.
    """
    queryset = Urgence.objects.all().order_by('ordre')
    serializer_class = UrgenceSerializer
    permission_classes = [permissions.IsAuthenticated]


class ReclamationViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des réclamations.

    Permissions:
    - Admin/Staff : accès à TOUTES les réclamations
    - Chef d'équipe : accès uniquement à SES réclamations créées
    - Client : accès uniquement à SES réclamations (créées par lui ou liées à lui)
    - Tout utilisateur authentifié peut créer une réclamation
    """
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = ['statut', 'site', 'zone', 'urgence', 'type_reclamation', 'createur']
    ordering_fields = ['date_creation', 'date_cloture_prevue']
    search_fields = ['numero_reclamation', 'description']

    def get_queryset(self):
        user = self.request.user
        # Optimisation: select_related pour éviter N+1 queries
        queryset = Reclamation.objects.filter(actif=True).select_related(
            'createur',
            'client__utilisateur',
            'site',
            'zone',
            'urgence',
            'type_reclamation',
            'equipe_affectee',
            'equipe_affectee__superviseur__utilisateur'
        )

        # Prefetch pour le détail (historique, photos, taches, satisfaction)
        if self.action in ['retrieve', 'suivi']:
            from django.db.models import Prefetch
            from api_planification.models import Tache
            queryset = queryset.prefetch_related(
                'historique__auteur',
                'photos',
                'satisfaction',
                Prefetch(
                    'taches_correctives',
                    queryset=Tache.objects.filter(deleted_at__isnull=True).select_related(
                        'id_type_tache', 'id_equipe'
                    ).prefetch_related('equipes')
                )
            )

        # Admin / Staff : accès à TOUTES les réclamations
        if user.is_staff or user.is_superuser:
            return queryset

        # Superviseur : accès aux réclamations de ses équipes
        if hasattr(user, 'superviseur_profile'):
            try:
                superviseur = user.superviseur_profile
                equipes_ids = list(superviseur.equipes_gerees.filter(actif=True).values_list('id', flat=True))
                if equipes_ids:
                    return queryset.filter(Q(equipe_affectee_id__in=equipes_ids) | Q(createur=user))
                return queryset.filter(createur=user)
            except AttributeError:
                return queryset.filter(createur=user)

        # Client : accès à ses réclamations uniquement (créées par lui ou liées à lui)
        if hasattr(user, 'client_profile'):
            return queryset.filter(Q(client=user.client_profile) | Q(createur=user))

        # Tout autre utilisateur : réclamations qu'il a créées
        return queryset.filter(createur=user)

    def perform_destroy(self, instance):
        """Soft delete instead of physical deletion."""
        instance.actif = False
        instance.save()

    def get_serializer_class(self):
        if self.action == 'list':
            return ReclamationListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return ReclamationCreateSerializer
        return ReclamationDetailSerializer

    def perform_create(self, serializer):
        """
        Assigner automatiquement le créateur (utilisateur connecté).
        Si c'est un client, on associe aussi le client_profile.
        Remplir automatiquement date_constatation si non fournie.
        """
        user = self.request.user
        extra_kwargs = {'createur': user}

        # Si l'utilisateur est un client, on associe également le client_profile
        if hasattr(user, 'client_profile'):
            extra_kwargs['client'] = user.client_profile

        # Remplir automatiquement date_constatation avec la date actuelle si non fournie
        if 'date_constatation' not in serializer.validated_data or not serializer.validated_data['date_constatation']:
            extra_kwargs['date_constatation'] = timezone.now()

        reclamation = serializer.save(**extra_kwargs)

        # Création de l'historique initial
        HistoriqueReclamation.objects.create(
            reclamation=reclamation,
            statut_precedent=None,
            statut_nouveau=reclamation.statut,
            auteur=user if user.is_authenticated else None,
            commentaire="Création de la réclamation"
        )

    def perform_update(self, serializer):
        # Récupération de l'instance avant modification pour comparer le statut
        instance = self.get_object()
        old_statut = instance.statut
        
        # Mise à jour automatique des dates selon le statut
        new_statut = serializer.validated_data.get('statut')
        if new_statut and new_statut != old_statut:
            if new_statut == 'PRISE_EN_COMPTE' and not instance.date_prise_en_compte:
                serializer.validated_data['date_prise_en_compte'] = timezone.now()
            elif new_statut == 'EN_COURS' and not instance.date_debut_traitement:
                serializer.validated_data['date_debut_traitement'] = timezone.now()
            elif new_statut == 'RESOLUE' and not instance.date_resolution:
                serializer.validated_data['date_resolution'] = timezone.now()
            elif new_statut == 'CLOTUREE' and not instance.date_cloture_reelle:
                serializer.validated_data['date_cloture_reelle'] = timezone.now()

        updated_instance = serializer.save()
        
        # Si le statut a changé, on ajoute une entrée dans l'historique
        if old_statut != updated_instance.statut:
            HistoriqueReclamation.objects.create(
                reclamation=updated_instance,
                statut_precedent=old_statut,
                statut_nouveau=updated_instance.statut,
                auteur=self.request.user if self.request.user.is_authenticated else None,
                commentaire=f"Changement de statut : {old_statut} -> {updated_instance.statut}"
            )


    @action(detail=True, methods=['get'])
    def suivi(self, request, pk=None):
        """
        Endpoint spécifique pour le suivi temps réel.
        Retourne la timeline et le statut (à enrichir selon besoin).
        """
        reclamation = self.get_object()
        serializer = ReclamationDetailSerializer(reclamation)
        return Response(serializer.data)

    @action(detail=True, methods=['put'])
    def assignation(self, request, pk=None):
        """
        Endpoint pour assigner une réclamation à une équipe.
        Met à jour la réclamation, les tâches associées, et l'historique.
        """
        reclamation = self.get_object()
        equipe_id = request.data.get('equipe_id')
        
        if not equipe_id:
             return Response({"error": "L'ID de l'équipe est requis."}, status=status.HTTP_400_BAD_REQUEST)
             
        try:
             equipe = Equipe.objects.get(pk=equipe_id)
        except Equipe.DoesNotExist:
             return Response({"error": "Équipe non trouvée."}, status=status.HTTP_404_NOT_FOUND)
             
        # Transaction atomique pour garantir la cohérence
        with transaction.atomic():
             old_statut = reclamation.statut
             old_equipe = reclamation.equipe_affectee
             
             # 1. Mise à jour de la Réclamation
             reclamation.equipe_affectee = equipe
             # Si nouvelle -> Prise en compte
             if reclamation.statut == 'NOUVELLE':
                 reclamation.statut = 'PRISE_EN_COMPTE'
                 if not reclamation.date_prise_en_compte:
                     reclamation.date_prise_en_compte = timezone.now()
             reclamation.save()
             
             # 2. Propagation aux Tâches (via le related_name 'taches_correctives')
             # On met à jour toutes les tâches correctives liées
             updated_count = reclamation.taches_correctives.update(id_equipe=equipe)
             
             # 3. Création de l'historique
             commentaire = f"Assignation à l'équipe: {equipe.nom_equipe}"
             if old_equipe:
                 commentaire += f" (anciennement: {old_equipe.nom_equipe})"
             
             if old_statut != reclamation.statut:
                 commentaire += f" - Statut changé de {old_statut} à {reclamation.statut}"

             HistoriqueReclamation.objects.create(
                reclamation=reclamation,
                statut_precedent=old_statut,
                statut_nouveau=reclamation.statut,
                auteur=request.user if request.user.is_authenticated else None,
                commentaire=commentaire
            )
            
        serializer = ReclamationDetailSerializer(reclamation)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def cloturer(self, request, pk=None):
        """
        Endpoint pour proposer la clôture d'une réclamation (ADMIN/SUPERVISEUR).

        Nouveau workflow (validation obligatoire par le créateur):
        1. Admin/Superviseur propose la clôture → statut EN_ATTENTE_VALIDATION_CLOTURE
        2. Le créateur valide via /valider_cloture/ → statut CLOTUREE
        """
        reclamation = self.get_object()

        # Vérification: seuls ADMIN/SUPERVISEUR peuvent proposer la clôture
        user = request.user
        is_admin = user.is_staff or user.is_superuser
        is_superviseur = hasattr(user, 'superviseur_profile')

        if not (is_admin or is_superviseur):
            return Response(
                {"error": "Seuls les administrateurs et superviseurs peuvent proposer la clôture."},
                status=status.HTTP_403_FORBIDDEN
            )

        with transaction.atomic():
            old_statut = reclamation.statut
            reclamation.statut = 'EN_ATTENTE_VALIDATION_CLOTURE'
            reclamation.cloture_proposee_par = user
            reclamation.date_proposition_cloture = timezone.now()
            if not reclamation.date_resolution:
                reclamation.date_resolution = timezone.now()
            reclamation.save()

            # Historique
            HistoriqueReclamation.objects.create(
                reclamation=reclamation,
                statut_precedent=old_statut,
                statut_nouveau='EN_ATTENTE_VALIDATION_CLOTURE',
                auteur=request.user,
                commentaire=f"Proposition de clôture par {user.get_full_name() or user.email}"
            )

        serializer = ReclamationDetailSerializer(reclamation)
        return Response({
            'message': 'Clôture proposée avec succès. En attente de validation par le créateur.',
            'reclamation': serializer.data
        })

    @action(detail=True, methods=['post'])
    def valider_cloture(self, request, pk=None):
        """
        Endpoint pour valider la clôture d'une réclamation (CREATEUR uniquement).

        Workflow:
        - Seul le créateur de la réclamation peut valider la clôture
        - La réclamation doit être en statut EN_ATTENTE_VALIDATION_CLOTURE
        - Passage au statut CLOTUREE définitif
        """
        reclamation = self.get_object()
        user = request.user

        # Vérification 1: L'utilisateur doit être le créateur de la réclamation
        if reclamation.createur != user:
            return Response(
                {"error": "Seul le créateur de la réclamation peut valider sa clôture."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Vérification 2: La réclamation doit être en attente de validation
        if reclamation.statut != 'EN_ATTENTE_VALIDATION_CLOTURE':
            return Response(
                {"error": f"La réclamation doit être en attente de validation de clôture. Statut actuel: {reclamation.get_statut_display()}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            old_statut = reclamation.statut
            reclamation.statut = 'CLOTUREE'
            reclamation.date_cloture_reelle = timezone.now()
            reclamation.save()

            # Historique
            HistoriqueReclamation.objects.create(
                reclamation=reclamation,
                statut_precedent=old_statut,
                statut_nouveau='CLOTUREE',
                auteur=user,
                commentaire=f"Clôture validée par le créateur {user.get_full_name() or user.email}"
            )

        serializer = ReclamationDetailSerializer(reclamation)
        return Response({
            'message': 'Clôture validée avec succès. La réclamation est définitivement clôturée.',
            'reclamation': serializer.data
        })

    @action(detail=False, methods=['post'], url_path='detect-site')
    def detect_site(self, request):
        """
        Endpoint pour détecter le site à partir d'une géométrie.
        Utilisé par le frontend pour afficher le site avant création.

        Body: { "geometry": { "type": "Point", "coordinates": [lng, lat] } }
        Returns: { "site_id": 1, "site_nom": "Nom du site" } ou { "site_id": null }
        """
        from django.contrib.gis.geos import GEOSGeometry
        from api.models import Site, SousSite
        import json

        geometry_data = request.data.get('geometry')
        if not geometry_data:
            return Response({"error": "Geometry is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Convertir le GeoJSON en objet GEOS
            geom = GEOSGeometry(json.dumps(geometry_data), srid=4326)
        except Exception as e:
            return Response({"error": f"Invalid geometry: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. D'abord chercher un SousSite qui contient la géométrie
        found_zone = SousSite.objects.filter(geometrie__intersects=geom).select_related('site').first()
        if found_zone and found_zone.site:
            return Response({
                "site_id": found_zone.site.id,
                "site_nom": found_zone.site.nom_site,
                "zone_id": found_zone.id,
                "zone_nom": found_zone.nom
            })

        # 2. Sinon chercher un Site dont l'emprise contient la géométrie
        found_site = Site.objects.filter(geometrie_emprise__intersects=geom).first()
        if found_site:
            return Response({
                "site_id": found_site.id,
                "site_nom": found_site.nom_site,
                "zone_id": None,
                "zone_nom": None
            })

        # 3. Aucun site trouvé
        return Response({
            "site_id": None,
            "site_nom": None,
            "zone_id": None,
            "zone_nom": None
        })

    @action(detail=False, methods=['get'])
    def map(self, request):
        """
        Endpoint pour afficher les réclamations sur la carte.

        Retourne un GeoJSON FeatureCollection avec les réclamations:
        - Qui ont une localisation (geometry non null)
        - Qui ne sont pas CLOTUREE (disparaissent après clôture)

        Query params optionnels:
        - bbox: Bounding box au format "west,south,east,north"
        - statut: Filtrer par statut spécifique

        Chaque feature inclut:
        - La géométrie de la réclamation
        - Les propriétés: id, numero, statut, urgence, couleur_statut
        """
        from django.contrib.gis.geos import Polygon
        import json

        # Couleurs par statut (du plus urgent au moins urgent)
        STATUT_COLORS = {
            'NOUVELLE': '#ef4444',        # Rouge vif - nouvelle réclamation
            'PRISE_EN_COMPTE': '#f97316', # Orange - en cours de prise en compte
            'EN_COURS': '#eab308',         # Jaune - en cours de traitement
            'RESOLUE': '#22c55e',          # Vert - résolue, en attente de clôture
            'REJETEE': '#6b7280',          # Gris - rejetée
            # CLOTUREE n'est pas affiché sur la carte
        }

        # Base queryset - exclure les réclamations clôturées et celles sans localisation
        queryset = self.get_queryset().exclude(
            statut='CLOTUREE'
        ).exclude(
            localisation__isnull=True
        ).select_related(
            'urgence', 'type_reclamation', 'site', 'zone'
        )

        # Filtre par statut si spécifié
        statut_filter = request.query_params.get('statut')
        if statut_filter:
            queryset = queryset.filter(statut=statut_filter)

        # Filtre par bbox si fourni
        bbox_str = request.query_params.get('bbox')
        if bbox_str:
            try:
                west, south, east, north = map(float, bbox_str.split(','))
                bbox_polygon = Polygon.from_bbox((west, south, east, north))
                queryset = queryset.filter(localisation__intersects=bbox_polygon)
            except (ValueError, AttributeError):
                pass  # Ignorer bbox invalide

        # Construire le GeoJSON
        features = []
        for rec in queryset[:200]:  # Limiter à 200 réclamations
            # Convertir la géométrie en GeoJSON
            geom_json = json.loads(rec.localisation.geojson)

            feature = {
                'type': 'Feature',
                'id': f'reclamation-{rec.id}',
                'geometry': geom_json,
                'properties': {
                    'id': rec.id,
                    'object_type': 'Reclamation',
                    'numero_reclamation': rec.numero_reclamation,
                    'statut': rec.statut,
                    'statut_display': dict(rec.STATUT_CHOICES).get(rec.statut, rec.statut),
                    'couleur_statut': STATUT_COLORS.get(rec.statut, '#6b7280'),
                    'urgence': rec.urgence.niveau_urgence if rec.urgence else None,
                    'urgence_couleur': rec.urgence.couleur if rec.urgence else None,
                    'type_reclamation': rec.type_reclamation.nom_reclamation if rec.type_reclamation else None,
                    'description': rec.description[:100] + '...' if rec.description and len(rec.description) > 100 else rec.description,
                    'site_nom': rec.site.nom_site if rec.site else None,
                    'zone_nom': rec.zone.nom if rec.zone else None,
                    'date_creation': rec.date_creation.isoformat() if rec.date_creation else None,
                }
            }
            features.append(feature)

        return Response({
            'type': 'FeatureCollection',
            'features': features,
            'count': len(features),
            'statut_colors': STATUT_COLORS
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Endpoint pour les statistiques des réclamations (User 6.6.14).
        Filtres: date_debut, date_fin, site, zone, type_reclamation
        """
        queryset = self.get_queryset()
        
        # Filtres temporels
        date_debut = request.query_params.get('date_debut')
        date_fin = request.query_params.get('date_fin')
        if date_debut:
            queryset = queryset.filter(date_creation__gte=date_debut)
        if date_fin:
            queryset = queryset.filter(date_creation__lte=date_fin)
        
        # Filtres géographiques
        site_id = request.query_params.get('site')
        zone_id = request.query_params.get('zone')
        if site_id:
            queryset = queryset.filter(site_id=site_id)
        if zone_id:
            queryset = queryset.filter(zone_id=zone_id)
        
        # Filtre type
        type_id = request.query_params.get('type_reclamation')
        if type_id:
            queryset = queryset.filter(type_reclamation_id=type_id)
        
        # Calcul des KPIs
        stats_data = {
            'total': queryset.count(),
            'par_statut': dict(queryset.values('statut').annotate(count=Count('id')).values_list('statut', 'count')),
            'par_type': list(queryset.values('type_reclamation__nom_reclamation').annotate(count=Count('id'))),
            'par_urgence': list(queryset.values('urgence__niveau_urgence').annotate(count=Count('id'))),
            'par_zone': list(queryset.filter(zone__isnull=False).values('zone__nom').annotate(count=Count('id'))),
        }
        
        # Délai moyen de traitement (pour les clôturées)
        cloturees = queryset.filter(statut='CLOTUREE', date_cloture_reelle__isnull=False)
        if cloturees.exists():
            delais = []
            for rec in cloturees:
                if rec.date_creation and rec.date_cloture_reelle:
                    delta = rec.date_cloture_reelle - rec.date_creation
                    delais.append(delta.total_seconds() / 3600)  # en heures
            if delais:
                stats_data['delai_moyen_heures'] = sum(delais) / len(delais)
        
        # Taux de satisfaction
        satisfactions = SatisfactionClient.objects.filter(reclamation__in=queryset)
        if satisfactions.exists():
            stats_data['satisfaction_moyenne'] = satisfactions.aggregate(Avg('note'))['note__avg']
            stats_data['nombre_evaluations'] = satisfactions.count()
        
        return Response(stats_data)


# ==============================================================================
# VIEWSET - SATISFACTION CLIENT (User 6.6.13)
# ==============================================================================

class SatisfactionClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des évaluations de satisfaction client.

    Permissions:
    - **Création/Modification/Suppression**: SEUL le créateur de la réclamation
    - **Lecture**: Le créateur + superviseur de l'équipe + ADMIN (retour d'expérience)
    """
    queryset = SatisfactionClient.objects.all()
    serializer_class = SatisfactionClientSerializer
    permission_classes = [IsReclamationCreatorOrTeamReader]

    def get_queryset(self):
        """
        Retourne les évaluations accessibles par l'utilisateur:
        - Ses propres évaluations (créateur)
        - Les évaluations des réclamations traitées par ses équipes (superviseur)
        - Toutes les évaluations (ADMIN/Staff)
        """
        user = self.request.user

        # ADMIN/Staff: accès à toutes les évaluations
        if user.is_staff or user.is_superuser:
            queryset = SatisfactionClient.objects.all()
        else:
            # Filtres cumulatifs (OR)
            from django.db.models import Q

            filters = Q(reclamation__createur=user)  # Évaluations créées par l'utilisateur

            # Si superviseur: ajouter les évaluations des réclamations de ses équipes
            if hasattr(user, 'superviseur_profile'):
                superviseur = user.superviseur_profile
                # Réclamations traitées par les équipes gérées par ce superviseur
                filters |= Q(reclamation__equipe_affectee__superviseur=superviseur)

            queryset = SatisfactionClient.objects.filter(filters)

        # Optimisation: select_related pour éviter N+1
        queryset = queryset.select_related(
            'reclamation',
            'reclamation__createur',
            'reclamation__equipe_affectee',
            'reclamation__equipe_affectee__superviseur'
        )

        # Filtre optionnel par reclamation_id
        reclamation_id = self.request.query_params.get('reclamation')
        if reclamation_id:
            queryset = queryset.filter(reclamation_id=reclamation_id)

        return queryset

    def create(self, request, *args, **kwargs):
        """
        Surcharge du create pour gérer l'unicité (OneToOne) de manière gracieuse.
        Si une évaluation existe déjà, on la met à jour.

        Validation: SEUL le créateur de la réclamation peut créer/modifier son évaluation.
        """
        reclamation_id = request.data.get('reclamation')
        if not reclamation_id:
            return Response({"detail": "Le champ réclamation est requis."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Vérifier que la réclamation existe
            reclamation = Reclamation.objects.get(pk=reclamation_id)
        except Reclamation.DoesNotExist:
            return Response({"detail": "Réclamation non trouvée."}, status=status.HTTP_404_NOT_FOUND)

        # VALIDATION CRITIQUE: Vérifier que l'utilisateur est bien le créateur de la réclamation
        if reclamation.createur != request.user:
            return Response(
                {"detail": "Vous ne pouvez évaluer que vos propres réclamations."},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            # On utilise update_or_create pour éviter les erreurs 400 de doublons
            satisfaction, created = SatisfactionClient.objects.update_or_create(
                reclamation_id=reclamation_id,
                defaults={
                    'note': request.data.get('note'),
                    'commentaire': request.data.get('commentaire', '')
                }
            )
            serializer = self.get_serializer(satisfaction)
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
