from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .serializers import UtilisateurSerializer
from .models import Equipe, Operateur

# Endpoint pour récupérer le profil utilisateur connecté
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import Utilisateur
        # Refetch user avec prefetch pour éviter N+1 sur les rôles
        user = Utilisateur.objects.prefetch_related(
            'roles_utilisateur__role'
        ).get(pk=request.user.pk)

        roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

        # Les superusers Django sont traités comme ADMIN dans l'application
        if user.is_superuser and 'ADMIN' not in roles:
            roles.append('ADMIN')

        serializer = UtilisateurSerializer(user)
        data = serializer.data

        # Si l'utilisateur est superviseur, ajouter les équipes qu'il gère
        if 'SUPERVISEUR' in roles:
            try:
                superviseur = user.superviseur_profile
                equipes_gerees = superviseur.equipes_gerees.filter(
                    actif=True
                ).values('id', 'nom_equipe')
                data['equipes_gerees'] = list(equipes_gerees)
            except AttributeError:  # Pas de profil superviseur
                data['equipes_gerees'] = []

        # Si l'utilisateur est client, ajouter l'ID du profil client
        if 'CLIENT' in roles:
            try:
                client_profile = user.client_profile
                data['client_id'] = client_profile.id
            except AttributeError:  # Pas de profil client
                data['client_id'] = None

        return Response(data)











# api_users/views.py
from rest_framework import viewsets, generics, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q, Count, Prefetch

from .models import (
    Utilisateur, Role, UtilisateurRole, StructureClient, Client, Superviseur, Operateur,
    Competence, CompetenceOperateur, Equipe, Absence, HoraireTravail, JourFerie,
    HistoriqueEquipeOperateur, StatutAbsence, StatutOperateur, NiveauCompetence
)
from .serializers import (
    UtilisateurSerializer, UtilisateurCreateSerializer, UtilisateurUpdateSerializer,
    ChangePasswordSerializer, AdminResetPasswordSerializer, RoleSerializer, UtilisateurRoleSerializer,
    StructureClientSerializer, StructureClientDetailSerializer,
    StructureClientCreateSerializer, StructureClientUpdateSerializer,
    ClientSerializer, ClientCreateSerializer, ClientWithStructureCreateSerializer,
    SuperviseurSerializer, SuperviseurCreateSerializer,
    CompetenceSerializer, CompetenceOperateurSerializer, CompetenceOperateurUpdateSerializer,
    OperateurListSerializer, OperateurDetailSerializer,
    OperateurCreateSerializer, OperateurUpdateSerializer,
    EquipeListSerializer, EquipeDetailSerializer,
    EquipeCreateSerializer, EquipeUpdateSerializer, AffecterMembresSerializer,
    HoraireTravailSerializer, HoraireTravailCreateSerializer, HoraireTravailUpdateSerializer,
    JourFerieSerializer, JourFerieCreateSerializer, JourFerieUpdateSerializer,
    AbsenceSerializer, AbsenceCreateSerializer, AbsenceValidationSerializer,
    HistoriqueEquipeOperateurSerializer
)
from .filters import (
    UtilisateurFilter, OperateurFilter, EquipeFilter, AbsenceFilter,
    CompetenceFilter, HistoriqueEquipeFilter
)
from .permissions import (
    IsAdmin, IsSuperviseur, IsClient,
    IsSuperviseurAndOwnsOperateur, IsSuperviseurAndOwnsEquipe,
    IsAdminOrReadOnly, IsSelfOrAdmin, IsSuperviseurAndOwnsAbsence
)
from .mixins import RoleBasedQuerySetMixin, RoleBasedPermissionMixin


# ==============================================================================
# VUES UTILISATEUR
# ==============================================================================

class UtilisateurViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des utilisateurs.

    list: Liste tous les utilisateurs
    create: Crée un nouvel utilisateur
    retrieve: Détail d'un utilisateur
    update: Met à jour un utilisateur
    destroy: Désactive un utilisateur (soft delete)

    Permissions:
    - ADMIN: accès complet CRUD
    - SUPERVISEUR: lecture seule (utilisateurs de leurs sites)
    """
    queryset = Utilisateur.objects.all().order_by('nom', 'prenom')
    filterset_class = UtilisateurFilter

    def get_permissions(self):
        """
        Permissions dynamiques selon l'action.
        """
        if self.action in ['list', 'retrieve']:
            # SUPERVISEUR peut lire
            return [IsAuthenticated()]
        else:
            # Seul ADMIN peut créer/modifier/supprimer
            return [IsAdmin()]

    def get_queryset(self):
        """
        Filtre les utilisateurs selon le rôle.
        - ADMIN: voit tous les utilisateurs
        - SUPERVISEUR: voit les utilisateurs de ses sites (superviseurs, clients)
        """
        qs = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return qs.none()

        roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

        # ADMIN voit tout
        if 'ADMIN' in roles:
            return qs

        # SUPERVISEUR voit les utilisateurs de ses sites
        if 'SUPERVISEUR' in roles:
            try:
                superviseur = user.superviseur_profile
                from api.models import Site

                # Sites supervisés
                mes_sites = Site.objects.filter(superviseur=superviseur)

                # IDs des clients et superviseurs de ces sites
                client_ids = mes_sites.values_list('client__utilisateur_id', flat=True)
                superviseur_ids = mes_sites.values_list('superviseur__utilisateur_id', flat=True)

                # Le superviseur peut voir:
                # - Lui-même
                # - Les clients de ses sites
                # - Les autres superviseurs de ses sites
                return qs.filter(
                    Q(id=user.id) |  # Lui-même
                    Q(id__in=client_ids) |  # Clients de ses sites
                    Q(id__in=superviseur_ids)  # Superviseurs de ses sites
                ).distinct()
            except AttributeError:
                return qs.filter(id=user.id)

        # CLIENT ou autre : Seulement lui-même
        return qs.filter(id=user.id)

    @action(detail=True, methods=['post'])
    def retirer_role(self, request, pk=None):
        """Retire un rôle à un utilisateur."""
        user = self.get_object()
        role_id = request.data.get('role_id')

        try:
            role = Role.objects.get(pk=role_id)
        except Role.DoesNotExist:
            return Response(
                {'error': 'Rôle non trouvé.'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            ur = UtilisateurRole.objects.get(utilisateur=user, role=role)
            ur.delete()

            # Retirer is_superuser/is_staff si on enlève le rôle ADMIN
            if role.nom_role == 'ADMIN' and user.is_superuser:
                user.is_superuser = False
                user.is_staff = False
                user.save(update_fields=['is_superuser', 'is_staff'])

            return Response({'message': f'Rôle {role.nom_role} retiré avec succès.'})
        except UtilisateurRole.DoesNotExist:
            return Response({'error': "L'utilisateur ne possède pas ce rôle."}, status=status.HTTP_400_BAD_REQUEST)

    def get_serializer_class(self):
        if self.action == 'create':
            return UtilisateurCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UtilisateurUpdateSerializer
        return UtilisateurSerializer

    def destroy(self, request, *args, **kwargs):
        """Soft delete: désactive l'utilisateur au lieu de le supprimer."""
        instance = self.get_object()
        instance.actif = False
        instance.save()
        return Response(
            {'message': 'Utilisateur désactivé avec succès.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def change_password(self, request, pk=None):
        """Change le mot de passe d'un utilisateur."""
        user = self.get_object()
        serializer = ChangePasswordSerializer(data=request.data)

        if serializer.is_valid():
            if not user.check_password(serializer.validated_data['old_password']):
                return Response(
                    {'old_password': 'Mot de passe incorrect.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({'message': 'Mot de passe modifié avec succès.'})

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def admin_reset_password(self, request, pk=None):
        """
        Réinitialise le mot de passe d'un utilisateur (réservé aux administrateurs).
        Ne nécessite pas l'ancien mot de passe.
        """
        user = self.get_object()
        serializer = AdminResetPasswordSerializer(data=request.data)

        if serializer.is_valid():
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({
                'message': f'Mot de passe réinitialisé avec succès pour {user.get_full_name()}.'
            })

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def activer(self, request, pk=None):
        """Réactive un utilisateur désactivé."""
        user = self.get_object()
        user.actif = True
        user.save()
        return Response({'message': 'Utilisateur réactivé avec succès.'})

    @action(detail=True, methods=['get'])
    def roles(self, request, pk=None):
        """Liste les rôles d'un utilisateur."""
        user = self.get_object()
        roles = UtilisateurRole.objects.filter(utilisateur=user)
        serializer = UtilisateurRoleSerializer(roles, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def attribuer_role(self, request, pk=None):
        """Attribue un rôle à un utilisateur."""
        user = self.get_object()
        role_id = request.data.get('role_id')

        try:
            role = Role.objects.get(pk=role_id)
        except Role.DoesNotExist:
            return Response(
                {'error': 'Rôle non trouvé.'},
                status=status.HTTP_404_NOT_FOUND
            )

        ur, created = UtilisateurRole.objects.get_or_create(
            utilisateur=user,
            role=role
        )

        # Synchroniser is_superuser/is_staff pour les ADMIN
        if role.nom_role == 'ADMIN' and not user.is_superuser:
            user.is_superuser = True
            user.is_staff = True
            user.save(update_fields=['is_superuser', 'is_staff'])

        if created:
            return Response({'message': f'Rôle {role.nom_role} attribué avec succès.'})
        return Response({'message': 'L\'utilisateur possède déjà ce rôle.'})


# ==============================================================================
# VUES ROLE
# ==============================================================================

class RoleViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des rôles."""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminOrReadOnly]


# ==============================================================================
# VUES STRUCTURE CLIENT
# ==============================================================================

class StructureClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des structures clientes.

    Une structure cliente représente une organisation (entreprise, mairie, etc.)
    qui peut avoir plusieurs utilisateurs (comptes de connexion).

    Permissions:
    - ADMIN: accès complet CRUD
    - CLIENT: lecture seule sur sa propre structure
    """
    permission_classes = [IsAuthenticated]
    queryset = StructureClient.objects.all()

    def get_queryset(self):
        """
        Filtre les structures selon le rôle de l'utilisateur.
        - ADMIN: voit toutes les structures
        - CLIENT: voit uniquement sa propre structure
        """
        qs = super().get_queryset()
        user = self.request.user

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # ADMIN voit tout (pas de filtre)
            if 'ADMIN' not in roles:
                # CLIENT voit uniquement sa propre structure
                if 'CLIENT' in roles:
                    try:
                        client_profile = user.client_profile
                        if client_profile.structure:
                            qs = qs.filter(id=client_profile.structure.id)
                        else:
                            return qs.none()
                    except AttributeError:
                        return qs.none()

                # SUPERVISEUR voit les structures de ses sites
                elif 'SUPERVISEUR' in roles:
                    try:
                        superviseur = user.superviseur_profile
                        qs = qs.filter(sites__superviseur=superviseur).distinct()
                    except AttributeError:
                        return qs.none()

        # ✅ Optimisation : Ajouter les compteurs via des annotations SQL
        # IMPORTANT: Ceci doit être fait APRÈS les filtres mais AVANT le return
        # distinct=True est crucial ici car on a deux jointures différentes
        return qs.annotate(
            annotated_utilisateurs_count=Count('utilisateurs', distinct=True),
            annotated_sites_count=Count('sites', distinct=True)
        )

    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action."""
        if self.action == 'create':
            return StructureClientCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return StructureClientUpdateSerializer
        elif self.action == 'retrieve':
            return StructureClientDetailSerializer
        return StructureClientSerializer

    def _is_client_only(self):
        """Vérifie si l'utilisateur est uniquement CLIENT (pas ADMIN)."""
        user = self.request.user
        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]
            return 'CLIENT' in roles and 'ADMIN' not in roles
        return False

    def create(self, request, *args, **kwargs):
        """CLIENT ne peut pas créer de structure."""
        if self._is_client_only():
            return Response(
                {"detail": "Les clients ne peuvent pas créer de structures."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """CLIENT ne peut pas modifier une structure."""
        if self._is_client_only():
            return Response(
                {"detail": "Les clients ne peuvent pas modifier les structures."},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """CLIENT ne peut pas supprimer une structure."""
        if self._is_client_only():
            return Response(
                {"detail": "Les clients ne peuvent pas supprimer les structures."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Soft delete: désactive la structure et tous ses utilisateurs
        structure = self.get_object()
        structure.actif = False
        structure.save()

        # Désactiver tous les utilisateurs de la structure
        for client in structure.utilisateurs.all():
            client.utilisateur.actif = False
            client.utilisateur.save()

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def utilisateurs(self, request, pk=None):
        """
        Liste les utilisateurs d'une structure.
        GET /api/users/structures/{id}/utilisateurs/
        """
        structure = self.get_object()
        clients = structure.utilisateurs.select_related('utilisateur').all()
        serializer = ClientSerializer(clients, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def ajouter_utilisateur(self, request, pk=None):
        """
        Ajoute un utilisateur à cette structure.
        POST /api/users/structures/{id}/ajouter_utilisateur/

        Body: { email, nom, prenom, password }
        """
        if self._is_client_only():
            return Response(
                {"detail": "Les clients ne peuvent pas ajouter d'utilisateurs."},
                status=status.HTTP_403_FORBIDDEN
            )

        structure = self.get_object()

        # Ajouter l'ID de la structure aux données
        data = request.data.copy()
        data['structure_id'] = structure.id

        serializer = ClientCreateSerializer(data=data)
        if serializer.is_valid():
            client = serializer.save()
            return Response(
                ClientSerializer(client).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==============================================================================
# VUES CLIENT (Utilisateur d'une Structure)
# ==============================================================================

class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des clients.

    Gère le CRUD complet des clients avec leur profil utilisateur associé.

    Permissions:
    - ADMIN: accès complet CRUD
    - CLIENT: lecture seule sur son propre profil (filtré par get_queryset)

    Filtres disponibles:
    - structure: filtre par ID de structure
    - structure__isnull: filtre les clients sans structure (orphelins)
    """
    permission_classes = [IsAuthenticated]
    queryset = Client.objects.select_related('utilisateur', 'structure').prefetch_related(
        'utilisateur__roles_utilisateur__role'
    ).all()
    filterset_fields = {
        'structure': ['exact', 'isnull'],
    }

    def get_queryset(self):
        """
        Filtre les clients selon le rôle de l'utilisateur.
        - ADMIN: voit tous les clients
        - CLIENT: voit uniquement son propre profil
        """
        qs = super().get_queryset()
        user = self.request.user

        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

            # ADMIN voit tout
            if 'ADMIN' in roles:
                return qs

            # CLIENT voit uniquement son propre profil
            if 'CLIENT' in roles:
                try:
                    client_profile = user.client_profile
                    return qs.filter(id=client_profile.id)
                except AttributeError:  # Pas de profil client
                    return qs.none()

        return qs.none()

    def _is_client_only(self):
        """Vérifie si l'utilisateur est uniquement CLIENT (pas ADMIN)."""
        user = self.request.user
        if user.is_authenticated:
            roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]
            return 'CLIENT' in roles and 'ADMIN' not in roles
        return False

    def create(self, request, *args, **kwargs):
        """CLIENT ne peut pas créer de client."""
        if self._is_client_only():
            return Response(
                {'error': 'Vous n\'avez pas les droits pour créer un client.'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Si on utilise ClientWithStructureCreateSerializer, gérer manuellement la réponse
        if 'nom_structure' in request.data:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            client = serializer.save()
            # Utiliser ClientSerializer pour la réponse
            response_serializer = ClientSerializer(client)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """CLIENT ne peut pas modifier de client."""
        if self._is_client_only():
            return Response(
                {'error': 'Vous n\'avez pas les droits pour modifier un client.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """CLIENT ne peut pas modifier de client."""
        if self._is_client_only():
            return Response(
                {'error': 'Vous n\'avez pas les droits pour modifier un client.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)

    def get_serializer_class(self):
        if self.action == 'create':
            # Si nom_structure est présent, créer structure + utilisateur ensemble
            if self.request and hasattr(self.request, 'data'):
                if 'nom_structure' in self.request.data:
                    return ClientWithStructureCreateSerializer
            return ClientCreateSerializer
        return ClientSerializer

    def destroy(self, request, *args, **kwargs):
        """Soft delete: désactive l'utilisateur client. CLIENT ne peut pas supprimer."""
        if self._is_client_only():
            return Response(
                {'error': 'Vous n\'avez pas les droits pour supprimer un client.'},
                status=status.HTTP_403_FORBIDDEN
            )
        instance = self.get_object()
        instance.utilisateur.actif = False
        instance.utilisateur.save()
        return Response(
            {'message': 'Client désactivé avec succès.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'], url_path='inventory-stats')
    def inventory_stats(self, request, pk=None):
        """
        Retourne les statistiques d'inventaire pour un client, groupées par site.

        Structure de réponse:
        {
            "totalObjets": 350,
            "vegetation": {"total": 280, "byType": {"arbre": 100, ...}},
            "hydraulique": {"total": 70, "byType": {"puit": 20, ...}},
            "bySite": [
                {
                    "siteId": "1",
                    "siteName": "Site Villa 1",
                    "total": 150,
                    "vegetation": 120,
                    "hydraulique": 30,
                    "byType": {"arbre": 50, "gazon": 70, "puit": 30}
                },
                ...
            ]
        }
        """
        from api.models import Site, Objet
        from collections import defaultdict

        client = self.get_object()

        # Récupérer tous les sites du client via structure_client
        if not client.structure:
            return Response({
                'totalObjets': 0,
                'vegetation': {'total': 0, 'byType': {}},
                'hydraulique': {'total': 0, 'byType': {}},
                'bySite': []
            })

        sites = Site.objects.filter(structure_client=client.structure).prefetch_related('objets')

        if not sites.exists():
            return Response({
                'totalObjets': 0,
                'vegetation': {'total': 0, 'byType': {}},
                'hydraulique': {'total': 0, 'byType': {}},
                'bySite': []
            })

        # Types de végétation et hydraulique
        VEGETATION_TYPES = {'Arbre', 'Palmier', 'Gazon', 'Arbuste', 'Vivace', 'Cactus', 'Graminee'}
        HYDRAULIQUE_TYPES = {'Puit', 'Pompe', 'Vanne', 'Clapet', 'Ballon', 'Canalisation', 'Aspersion', 'Goutte'}

        # Totaux globaux
        global_vegetation_counts = defaultdict(int)
        global_hydraulique_counts = defaultdict(int)
        global_total_vegetation = 0
        global_total_hydraulique = 0

        # Stats par site
        by_site = []

        for site in sites:
            site_vegetation = 0
            site_hydraulique = 0
            site_by_type = defaultdict(int)

            # Compter les objets de ce site
            objets = site.objets.all()

            for obj in objets:
                type_name = obj.get_nom_type()

                if type_name in VEGETATION_TYPES:
                    type_key = type_name.lower()
                    site_by_type[type_key] += 1
                    site_vegetation += 1
                    global_vegetation_counts[type_key] += 1
                    global_total_vegetation += 1

                elif type_name in HYDRAULIQUE_TYPES:
                    type_key = type_name.lower()
                    site_by_type[type_key] += 1
                    site_hydraulique += 1
                    global_hydraulique_counts[type_key] += 1
                    global_total_hydraulique += 1

            # Ajouter les stats de ce site (seulement si le site a des objets)
            site_total = site_vegetation + site_hydraulique
            if site_total > 0:
                by_site.append({
                    'siteId': str(site.id),
                    'siteName': site.nom_site or f'Site {site.id}',
                    'total': site_total,
                    'vegetation': site_vegetation,
                    'hydraulique': site_hydraulique,
                    'byType': dict(site_by_type)
                })

        return Response({
            'totalObjets': global_total_vegetation + global_total_hydraulique,
            'vegetation': {
                'total': global_total_vegetation,
                'byType': dict(global_vegetation_counts)
            },
            'hydraulique': {
                'total': global_total_hydraulique,
                'byType': dict(global_hydraulique_counts)
            },
            'bySite': by_site
        })


# ==============================================================================
# VUES SUPERVISEUR
# ==============================================================================

class SuperviseurViewSet(RoleBasedQuerySetMixin, RoleBasedPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des superviseurs.

    Utilise le système de permissions unifié :
    - ADMIN : Accès complet (CRUD)
    - SUPERVISEUR : Lecture seule sur son propre profil
    - CLIENT : Aucun accès

    Le filtrage automatique est géré par RoleBasedQuerySetMixin.
    """
    queryset = Superviseur.objects.select_related('utilisateur').prefetch_related(
        'utilisateur__roles_utilisateur__role',
        'operateurs_supervises'
    ).all()

    # Permissions par action (utilise RoleBasedPermissionMixin)
    permission_classes_by_action = {
        'create': [IsAdmin],
        'update': [IsAdmin | IsSelfOrAdmin],
        'partial_update': [IsAdmin | IsSelfOrAdmin],
        'destroy': [IsAdmin],
        'default': [IsAdmin | IsSuperviseur],  # Lecture pour ADMIN et SUPERVISEUR
    }

    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action."""
        if self.action == 'create':
            return SuperviseurCreateSerializer
        return SuperviseurSerializer

    def perform_create(self, serializer):
        serializer.save()
        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()

    def perform_update(self, serializer):
        serializer.save()
        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()

    def destroy(self, request, *args, **kwargs):
        """Soft delete : désactive l'utilisateur superviseur."""
        instance = self.get_object()
        instance.utilisateur.actif = False
        instance.utilisateur.save()
        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()
        return Response(
            {'message': 'Superviseur désactivé avec succès.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'])
    def equipes(self, request, pk=None):
        """Liste les équipes gérées par ce superviseur."""
        superviseur = self.get_object()
        equipes = superviseur.equipes_gerees.filter(actif=True)
        serializer = EquipeListSerializer(equipes, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def operateurs(self, request, pk=None):
        """Liste les opérateurs supervisés par ce superviseur."""
        superviseur = self.get_object()
        operateurs = superviseur.operateurs_supervises.filter(statut='ACTIF')
        serializer = OperateurListSerializer(operateurs, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def statistiques(self, request, pk=None):
        """Retourne les statistiques du superviseur."""
        superviseur = self.get_object()
        today = timezone.now().date()

        # Statistiques équipes
        equipes_actives = superviseur.equipes_gerees.filter(actif=True)

        # Statistiques opérateurs
        operateurs_actifs = superviseur.operateurs_supervises.filter(statut='ACTIF')
        operateurs_disponibles = operateurs_actifs.exclude(
            absences__statut=StatutAbsence.VALIDEE,
            absences__date_debut__lte=today,
            absences__date_fin__gte=today
        ).distinct()

        # Absences en attente de validation
        absences_en_attente = Absence.objects.filter(
            operateur__superviseur=superviseur,
            statut=StatutAbsence.DEMANDEE
        ).count()

        # Absences en cours
        absences_en_cours = Absence.objects.filter(
            operateur__superviseur=superviseur,
            statut=StatutAbsence.VALIDEE,
            date_debut__lte=today,
            date_fin__gte=today
        ).count()

        return Response({
            'superviseur': SuperviseurSerializer(superviseur).data,
            'equipes': {
                'total': equipes_actives.count(),
                'actives': equipes_actives.count(),
            },
            'operateurs': {
                'total': operateurs_actifs.count(),
                'disponibles': operateurs_disponibles.count(),
                'absents': operateurs_actifs.count() - operateurs_disponibles.count(),
            },
            'absences': {
                'en_attente': absences_en_attente,
                'en_cours': absences_en_cours,
            }
        })

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Retourne le profil du superviseur connecté."""
        user = request.user

        if not hasattr(user, 'superviseur_profile'):
            return Response(
                {'error': 'Vous n\'avez pas de profil superviseur.'},
                status=status.HTTP_404_NOT_FOUND
            )

        superviseur = user.superviseur_profile
        serializer = SuperviseurSerializer(superviseur)
        return Response(serializer.data)


# ==============================================================================
# VUES COMPETENCE
# ==============================================================================

class CompetenceViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des compétences.

    Les compétences sont des référentiels utilisés pour qualifier les opérateurs.
    """
    queryset = Competence.objects.all()
    serializer_class = CompetenceSerializer
    filterset_class = CompetenceFilter

    @action(detail=True, methods=['get'])
    def operateurs(self, request, pk=None):
        """Liste les opérateurs ayant cette compétence."""
        competence = self.get_object()
        niveau_minimum = request.query_params.get('niveau_minimum')

        queryset = CompetenceOperateur.objects.filter(
            competence=competence
        ).exclude(niveau=NiveauCompetence.NON)

        if niveau_minimum:
            # Filtrer par niveau minimum
            niveaux_valides = self._get_niveaux_superieurs(niveau_minimum)
            queryset = queryset.filter(niveau__in=niveaux_valides)

        serializer = CompetenceOperateurSerializer(queryset, many=True)
        return Response(serializer.data)

    def _get_niveaux_superieurs(self, niveau):
        """Retourne les niveaux supérieurs ou égaux au niveau donné."""
        ordre = ['NON', 'DEBUTANT', 'INTERMEDIAIRE', 'EXPERT']
        try:
            idx = ordre.index(niveau)
            return ordre[idx:]
        except ValueError:
            return ordre


# ==============================================================================
# VUES OPERATEUR
# ==============================================================================

class OperateurViewSet(RoleBasedQuerySetMixin, RoleBasedPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des opérateurs (jardiniers).

    Implémente:
    - CRUD complet (US 5.5.0)
    - Gestion des compétences (US 5.5.1)
    - Filtrage par compétence/disponibilité

    Permissions (via RoleBasedPermissionMixin):
    - ADMIN: accès complet CRUD
    - SUPERVISEUR: lecture seule sur ses opérateurs

    Le filtrage automatique est géré par RoleBasedQuerySetMixin.
    """
    # ⚡ OPTIMISÉ: Précharger toutes les relations pour éviter N+1
    queryset = Operateur.objects.select_related(
        'superviseur__utilisateur', 'equipe', 'equipe_dirigee'  # ✅ Pour est_chef_equipe
    ).prefetch_related(
        'competences_operateur__competence',
        # ✅ Pour est_disponible: précharger les absences validées d'aujourd'hui
        Prefetch(
            'absences',
            queryset=Absence.objects.filter(statut='VALIDEE'),
            to_attr='absences_validees'
        )
    ).all()
    filterset_class = OperateurFilter

    # Permissions par action
    permission_classes_by_action = {
        'create': [IsAdmin],
        'update': [IsAdmin],
        'partial_update': [IsAdmin],
        'destroy': [IsAdmin],
        'affecter_competence': [IsAdmin],
        'modifier_niveau_competence': [IsAdmin],
        'default': [IsAuthenticated],  # Lecture pour tous authentifiés (filtrage via mixin)
    }

    def get_serializer_class(self):
        if self.action == 'create':
            return OperateurCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OperateurUpdateSerializer
        elif self.action == 'retrieve':
            return OperateurDetailSerializer
        return OperateurListSerializer

    def list(self, request, *args, **kwargs):
        """
        Liste les opérateurs (table HR uniquement).

        Dans la nouvelle architecture:
        - Operateur est une table HR sans lien avec Utilisateur
        - SUPERVISEUR ne voit que ses opérateurs (via RoleBasedQuerySetMixin)
        - ADMIN voit tous les opérateurs
        """
        # Liste les opérateurs (table HR uniquement, sans lien avec Utilisateur)
        qs_operateurs = self.filter_queryset(self.get_queryset())
        serializer = OperateurListSerializer(qs_operateurs, many=True)

        # Pagination standard
        page = self.paginate_queryset(qs_operateurs)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Soft delete: désactive l'opérateur.

        Vérifie s'il est chef d'équipe et avertit si nécessaire.
        Permission gérée par RoleBasedPermissionMixin (ADMIN only).
        """
        instance = self.get_object()

        # Vérifier s'il est chef d'équipe
        if hasattr(instance, 'equipe_dirigee') and instance.equipe_dirigee and instance.equipe_dirigee.actif:
            return Response(
                {
                    'warning': 'Cet opérateur est chef d\'équipe.',
                    'equipes': [instance.equipe_dirigee.nom_equipe],
                    'message': 'Veuillez d\'abord réassigner le chef de l\'équipe concernée.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Retirer de l'équipe actuelle
        if instance.equipe:
            # Fermer l'historique
            HistoriqueEquipeOperateur.objects.filter(
                operateur=instance,
                equipe=instance.equipe,
                date_fin__isnull=True
            ).update(date_fin=timezone.now().date())

            instance.equipe = None
            instance.save()

        # Désactiver l'opérateur (changer statut)
        instance.statut = 'INACTIF'
        instance.save()

        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()

        return Response(
            {'message': 'Opérateur désactivé avec succès.'},
            status=status.HTTP_200_OK
        )

    def perform_create(self, serializer):
        serializer.save()
        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()

    def perform_update(self, serializer):
        serializer.save()
        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()

    @action(detail=True, methods=['get'])
    def competences(self, request, pk=None):
        """Liste les compétences d'un opérateur."""
        operateur = self.get_object()
        competences = CompetenceOperateur.objects.filter(
            operateur=operateur
        ).select_related('competence')
        serializer = CompetenceOperateurSerializer(competences, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def affecter_competence(self, request, pk=None):
        """Affecte ou met à jour une compétence pour un opérateur. Permission: ADMIN only."""
        operateur = self.get_object()
        competence_id = request.data.get('competence_id')
        niveau = request.data.get('niveau', NiveauCompetence.DEBUTANT)

        try:
            competence = Competence.objects.get(pk=competence_id)
        except Competence.DoesNotExist:
            return Response(
                {'error': 'Compétence non trouvée.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # On utilise get_or_create pour garantir que 'created' existe toujours
        comp_op, created = CompetenceOperateur.objects.get_or_create(
            operateur=operateur,
            competence=competence,
            defaults={
                'niveau': niveau,
                'date_acquisition': timezone.now().date()
            }
        )
        if not created:
            # Si déjà existant, on met à jour le niveau si besoin
            comp_op.niveau = niveau
            comp_op.save()

        serializer = CompetenceOperateurSerializer(comp_op)
        return Response(serializer.data)

    @action(detail=True, methods=['put'])
    def modifier_niveau_competence(self, request, pk=None):
        """Modifie le niveau d'une compétence existante. Permission: ADMIN only."""
        operateur = self.get_object()
        competence_id = request.data.get('competence_id')
        niveau = request.data.get('niveau')

        try:
            comp_op = CompetenceOperateur.objects.get(
                operateur=operateur,
                competence_id=competence_id
            )
        except CompetenceOperateur.DoesNotExist:
            return Response(
                {'error': 'Cette compétence n\'est pas attribuée à cet opérateur.'},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = CompetenceOperateurUpdateSerializer(
            comp_op,
            data={'niveau': niveau},
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response(CompetenceOperateurSerializer(comp_op).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def absences(self, request, pk=None):
        """Liste les absences d'un opérateur."""
        operateur = self.get_object()
        absences = Absence.objects.filter(operateur=operateur)
        serializer = AbsenceSerializer(absences, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def historique_equipes(self, request, pk=None):
        """Retourne l'historique des équipes d'un opérateur."""
        operateur = self.get_object()
        historique = HistoriqueEquipeOperateur.objects.filter(
            operateur=operateur
        ).select_related('equipe')
        serializer = HistoriqueEquipeOperateurSerializer(historique, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def disponibles(self, request):
        """Liste les opérateurs disponibles aujourd'hui."""
        today = timezone.now().date()

        # Opérateurs actifs sans absence validée aujourd'hui
        operateurs = self.get_queryset().filter(
            statut='ACTIF'
        ).exclude(
            absences__statut=StatutAbsence.VALIDEE,
            absences__date_debut__lte=today,
            absences__date_fin__gte=today
        )

        serializer = OperateurListSerializer(operateurs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def chefs_potentiels(self, request):
        """Liste les opérateurs pouvant être chef d'équipe (tout opérateur actif)."""
        operateurs = self.get_queryset().filter(statut='ACTIF')
        serializer = OperateurListSerializer(operateurs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def par_competence(self, request):
        """Filtre les opérateurs par compétence et niveau."""
        competence_id = request.query_params.get('competence_id')
        competence_nom = request.query_params.get('competence_nom')
        niveau_minimum = request.query_params.get('niveau_minimum')
        disponible_uniquement = request.query_params.get('disponible_uniquement', 'false').lower() == 'true'

        queryset = self.get_queryset().filter(statut='ACTIF')

        # Filtrer par compétence
        if competence_id:
            queryset = queryset.filter(
                competences_operateur__competence_id=competence_id
            )
        elif competence_nom:
            queryset = queryset.filter(
                competences_operateur__competence__nom_competence__icontains=competence_nom
            )

        # Filtrer par niveau minimum
        if niveau_minimum:
            niveaux = ['NON', 'DEBUTANT', 'INTERMEDIAIRE', 'EXPERT']
            try:
                idx = niveaux.index(niveau_minimum)
                niveaux_valides = niveaux[idx:]
                queryset = queryset.filter(
                    competences_operateur__niveau__in=niveaux_valides
                )
            except ValueError:
                pass

        # Filtrer par disponibilité
        if disponible_uniquement:
            today = timezone.now().date()
            queryset = queryset.filter(statut='ACTIF').exclude(
                absences__statut=StatutAbsence.VALIDEE,
                absences__date_debut__lte=today,
                absences__date_fin__gte=today
            )

        queryset = queryset.distinct()
        serializer = OperateurListSerializer(queryset, many=True)
        return Response(serializer.data)


# ==============================================================================
# VUES EQUIPE
# ==============================================================================

class EquipeViewSet(RoleBasedQuerySetMixin, RoleBasedPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des équipes (US 5.5.2).

    Implémente:
    - CRUD équipes
    - Affectation des membres
    - Statut opérationnel dynamique

    Permissions (via RoleBasedPermissionMixin):
    - ADMIN: accès complet CRUD
    - SUPERVISEUR: lecture seule sur ses équipes

    Le filtrage automatique est géré par RoleBasedQuerySetMixin.
    """
    # ⚡ OPTIMISATION: Précharger TOUTES les relations pour éviter N+1
    queryset = Equipe.objects.select_related(
        'chef_equipe',
        'site_principal',  # ✅ Multi-site architecture: site principal
        'site_principal__superviseur__utilisateur',  # ✅ Pour superviseur_nom (évite N+1)
        'site__superviseur__utilisateur',  # ✅ Legacy fallback
    ).prefetch_related(
        'sites_secondaires',  # ✅ Multi-site architecture: sites secondaires
        # ✅ Pour statut_operationnel: précharger opérateurs + absences actives
        Prefetch(
            'operateurs',
            queryset=Operateur.objects.filter(statut='ACTIF').prefetch_related(
                Prefetch(
                    'absences',
                    queryset=Absence.objects.filter(statut='VALIDEE'),
                    to_attr='absences_validees'
                )
            ),
            to_attr='operateurs_actifs'
        )
    ).annotate(
        nombre_membres_count=Count('operateurs', filter=Q(operateurs__statut='ACTIF'))
    ).all()
    filterset_class = EquipeFilter

    # Permissions par action
    permission_classes_by_action = {
        'create': [IsAdmin],
        'update': [IsAdmin],
        'partial_update': [IsAdmin],
        'destroy': [IsAdmin],
        'affecter_membres': [IsAdmin],
        'retirer_membre': [IsAdmin],
        'default': [IsAuthenticated],  # Lecture pour tous authentifiés (filtrage via mixin)
    }

    def filter_queryset(self, queryset):
        """Override pour s'assurer que le filtrage django-filter est appliqué."""
        # ⚡ OPTIMISATION: Logs de debug désactivés car ils causaient un ralentissement de 22s
        # Les logs faisaient des .count() et des boucles sur toutes les équipes à chaque requête
        # Pour réactiver le debug, décommenter les lignes ci-dessous

        # import logging
        # logger = logging.getLogger(__name__)
        # user = self.request.user
        # roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()] if user.is_authenticated else []
        # logger.info(f"[EquipeViewSet] 👤 User: {user.email}, Roles: {roles}")

        # Appliquer le filtrage (django-filter + RoleBasedQuerySetMixin)
        filtered = super().filter_queryset(queryset)

        return filtered

    def get_serializer_class(self):
        if self.action == 'create':
            return EquipeCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return EquipeUpdateSerializer
        elif self.action == 'retrieve':
            return EquipeDetailSerializer
        return EquipeListSerializer

    def perform_create(self, serializer):
        serializer.save()
        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()

    def perform_update(self, serializer):
        serializer.save()
        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()

    def destroy(self, request, *args, **kwargs):
        """Désactive une équipe au lieu de la supprimer. Permission: ADMIN only."""
        instance = self.get_object()
        instance.actif = False
        instance.save()
        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()
        return Response(
            {'message': 'Équipe désactivée avec succès.'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['get'])
    def membres(self, request, pk=None):
        """Liste les membres d'une équipe."""
        equipe = self.get_object()
        membres = equipe.operateurs.filter(statut='ACTIF')
        serializer = OperateurListSerializer(membres, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def affecter_membres(self, request, pk=None):
        """Affecte des membres à une équipe. Permission: ADMIN only."""
        equipe = self.get_object()
        serializer = AffecterMembresSerializer(data=request.data)

        if serializer.is_valid():
            serializer.update_membres(equipe, serializer.validated_data['operateurs'])
            from greensig_web.cache_utils import invalidate_on_team_mutation
            invalidate_on_team_mutation()
            return Response({'message': 'Membres affectés avec succès.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def retirer_membre(self, request, pk=None):
        """Retire un membre d'une équipe. Permission: ADMIN only."""
        equipe = self.get_object()
        operateur_id = request.data.get('operateur_id')

        try:
            operateur = Operateur.objects.get(pk=operateur_id)
        except Operateur.DoesNotExist:
            return Response(
                {'error': 'Opérateur non trouvé.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if operateur.equipe != equipe:
            return Response(
                {'error': 'Cet opérateur n\'appartient pas à cette équipe.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Fermer l'historique
        HistoriqueEquipeOperateur.objects.filter(
            operateur=operateur,
            equipe=equipe,
            date_fin__isnull=True
        ).update(date_fin=timezone.now().date())

        operateur.equipe = None
        operateur.save()

        from greensig_web.cache_utils import invalidate_on_team_mutation
        invalidate_on_team_mutation()

        return Response({'message': 'Membre retiré de l\'équipe.'})

    @action(detail=True, methods=['get'])
    def statut(self, request, pk=None):
        """Retourne le statut opérationnel détaillé de l'équipe."""
        from django.db.models import Prefetch
        equipe = self.get_object()
        today = timezone.now().date()

        # Prefetch absences en cours pour éviter N+1
        absences_en_cours = Absence.objects.filter(
            statut=StatutAbsence.VALIDEE,
            date_debut__lte=today,
            date_fin__gte=today
        )
        membres = equipe.operateurs.filter(
            statut='ACTIF'
        ).select_related(
            'equipe'
        ).prefetch_related(
            Prefetch('absences', queryset=absences_en_cours, to_attr='absences_actuelles')
        )

        total = membres.count()
        disponibles = []
        absents = []

        for membre in membres:
            # Utilise le prefetch au lieu de requête
            absence = membre.absences_actuelles[0] if membre.absences_actuelles else None

            if absence:
                absents.append({
                    'operateur': OperateurListSerializer(membre).data,
                    'absence': AbsenceSerializer(absence).data
                })
            else:
                disponibles.append(OperateurListSerializer(membre).data)

        return Response({
            'equipe': EquipeListSerializer(equipe).data,
            'statut_operationnel': equipe.statut_operationnel,
            'total_membres': total,
            'disponibles_count': len(disponibles),
            'absents_count': len(absents),
            'disponibles': disponibles,
            'absents': absents
        })

    @action(detail=True, methods=['get'])
    def historique(self, request, pk=None):
        """Retourne l'historique des membres de l'équipe."""
        equipe = self.get_object()
        historique = HistoriqueEquipeOperateur.objects.filter(
            equipe=equipe
        ).select_related('operateur', 'equipe')
        serializer = HistoriqueEquipeOperateurSerializer(historique, many=True)
        return Response(serializer.data)


# ==============================================================================
# VUES HORAIRE TRAVAIL (PHASE 2)
# ==============================================================================

class HoraireTravailViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des horaires de travail des équipes.

    ✅ PHASE 2: Permet de définir et gérer les horaires de travail par équipe et jour.
    Ces horaires sont utilisés pour calculer la charge réelle lors de la génération
    de tâches récurrentes.

    Permissions:
    - ADMIN: accès complet CRUD
    - SUPERVISEUR: lecture seule sur les horaires de ses équipes
    - Autres: lecture seule
    """
    queryset = HoraireTravail.objects.select_related('equipe').all()
    filterset_fields = ['equipe', 'jour_semaine', 'actif']
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action."""
        if self.action == 'create':
            return HoraireTravailCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return HoraireTravailUpdateSerializer
        return HoraireTravailSerializer

    def get_queryset(self):
        """Filtre les horaires selon le rôle de l'utilisateur."""
        user = self.request.user
        queryset = super().get_queryset()

        # Récupérer les rôles
        roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]

        # ADMIN voit tout
        if 'ADMIN' in roles:
            return queryset

        # SUPERVISEUR voit les horaires des équipes de ses sites uniquement
        if 'SUPERVISEUR' in roles and hasattr(user, 'superviseur_profile'):
            superviseur = user.superviseur_profile
            return queryset.filter(
                Q(equipe__site_principal__superviseur=superviseur) |
                Q(equipe__sites_secondaires__superviseur=superviseur) |
                Q(equipe__site__superviseur=superviseur)  # champ legacy
            ).distinct()

        # Autres utilisateurs voient les horaires de toutes les équipes (lecture seule)
        return queryset

    def get_permissions(self):
        """Permissions dynamiques : seul ADMIN peut créer/modifier/supprimer."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def par_equipe(self, request):
        """
        Retourne les horaires groupés par équipe.

        Query params:
        - equipe_id: Filtre par ID d'équipe (optionnel)
        """
        equipe_id = request.query_params.get('equipe_id')
        queryset = self.get_queryset()

        if equipe_id:
            queryset = queryset.filter(equipe_id=equipe_id)

        # Grouper par équipe
        from collections import defaultdict
        horaires_par_equipe = defaultdict(list)

        for horaire in queryset:
            horaires_par_equipe[horaire.equipe.id].append(HoraireTravailSerializer(horaire).data)

        result = []
        for equipe_id, horaires in horaires_par_equipe.items():
            equipe = Equipe.objects.get(id=equipe_id)
            result.append({
                'equipe': {
                    'id': equipe.id,
                    'nom_equipe': equipe.nom_equipe
                },
                'horaires': horaires
            })

        return Response(result)

    @action(detail=False, methods=['post'])
    def creer_semaine_complete(self, request):
        """
        Crée les horaires pour toute une semaine d'un coup.

        Body:
        {
            "equipe": 1,
            "lundi_vendredi": {
                "heure_debut": "08:00",
                "heure_fin": "17:00",
                "duree_pause_minutes": 60
            },
            "samedi": {
                "heure_debut": "08:00",
                "heure_fin": "12:00",
                "duree_pause_minutes": 0
            },
            "dimanche": null  // Pas de travail le dimanche
        }
        """
        equipe_id = request.data.get('equipe')
        lundi_vendredi = request.data.get('lundi_vendredi')
        samedi = request.data.get('samedi')
        dimanche = request.data.get('dimanche')

        if not equipe_id:
            return Response(
                {'error': 'Le champ "equipe" est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            equipe = Equipe.objects.get(id=equipe_id)
        except Equipe.DoesNotExist:
            return Response(
                {'error': 'Équipe non trouvée.'},
                status=status.HTTP_404_NOT_FOUND
            )

        horaires_crees = []
        jours_mapping = {
            'LUN': lundi_vendredi,
            'MAR': lundi_vendredi,
            'MER': lundi_vendredi,
            'JEU': lundi_vendredi,
            'VEN': lundi_vendredi,
            'SAM': samedi,
            'DIM': dimanche,
        }

        for jour, config in jours_mapping.items():
            if config is None:
                continue

            # Supprimer l'ancien horaire actif si existe
            HoraireTravail.objects.filter(
                equipe=equipe,
                jour_semaine=jour,
                actif=True
            ).delete()

            # Créer le nouvel horaire
            horaire = HoraireTravail.objects.create(
                equipe=equipe,
                jour_semaine=jour,
                heure_debut=config['heure_debut'],
                heure_fin=config['heure_fin'],
                duree_pause_minutes=config.get('duree_pause_minutes', 60),
                actif=True
            )
            horaires_crees.append(horaire)

        serializer = HoraireTravailSerializer(horaires_crees, many=True)
        return Response({
            'message': f'{len(horaires_crees)} horaires créés avec succès.',
            'horaires': serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], permission_classes=[IsAdmin])
    def creer_semaine_globale(self, request):
        """
        ✅ NOUVEAU: Crée les horaires pour toutes les équipes actives en une seule fois.

        Permet de configurer rapidement toutes les équipes avec les mêmes horaires,
        avec possibilité d'exclure certaines équipes.

        Body:
        {
            "lundi_vendredi": {
                "heure_debut": "08:00",
                "heure_fin": "17:00",
                "duree_pause_minutes": 60
            },
            "samedi": {
                "heure_debut": "08:00",
                "heure_fin": "12:00",
                "duree_pause_minutes": 0
            },
            "dimanche": null,
            "equipes_exclues": [1, 5, 12]  // IDs des équipes à ne pas configurer (optionnel)
        }

        Returns:
        {
            "message": "Horaires créés pour 25 équipes sur 28 actives.",
            "equipes_configurees": 25,
            "equipes_actives": 28,
            "equipes_exclues": 3,
            "details": [...]
        }
        """
        lundi_vendredi = request.data.get('lundi_vendredi')
        samedi = request.data.get('samedi')
        dimanche = request.data.get('dimanche')
        equipes_exclues = request.data.get('equipes_exclues', [])

        if not lundi_vendredi:
            return Response(
                {'error': 'Le champ "lundi_vendredi" est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Récupérer toutes les équipes actives
        equipes = Equipe.objects.filter(actif=True)
        if equipes_exclues:
            equipes = equipes.exclude(id__in=equipes_exclues)

        equipes_count = equipes.count()
        equipes_actives_total = Equipe.objects.filter(actif=True).count()

        if equipes_count == 0:
            return Response(
                {'error': 'Aucune équipe à configurer après exclusions.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        jours_mapping = {
            'LUN': lundi_vendredi,
            'MAR': lundi_vendredi,
            'MER': lundi_vendredi,
            'JEU': lundi_vendredi,
            'VEN': lundi_vendredi,
            'SAM': samedi,
            'DIM': dimanche,
        }

        total_horaires_crees = 0
        details_equipes = []

        for equipe in equipes:
            horaires_equipe = []

            for jour, config in jours_mapping.items():
                if config is None:
                    continue

                # Supprimer l'ancien horaire actif si existe
                HoraireTravail.objects.filter(
                    equipe=equipe,
                    jour_semaine=jour,
                    actif=True
                ).delete()

                # Créer le nouvel horaire
                horaire = HoraireTravail.objects.create(
                    equipe=equipe,
                    jour_semaine=jour,
                    heure_debut=config['heure_debut'],
                    heure_fin=config['heure_fin'],
                    duree_pause_minutes=config.get('duree_pause_minutes', 60),
                    actif=True
                )
                horaires_equipe.append(horaire)

            total_horaires_crees += len(horaires_equipe)
            details_equipes.append({
                'equipe_id': equipe.id,
                'equipe_nom': equipe.nom_equipe,
                'horaires_crees': len(horaires_equipe)
            })

        return Response({
            'message': f'Horaires créés pour {equipes_count} équipe(s) sur {equipes_actives_total} active(s).',
            'equipes_configurees': equipes_count,
            'equipes_actives': equipes_actives_total,
            'equipes_exclues': len(equipes_exclues),
            'total_horaires_crees': total_horaires_crees,
            'details': details_equipes
        }, status=status.HTTP_201_CREATED)


# ==============================================================================
# VUES JOUR FERIE (PHASE 3)
# ==============================================================================

class JourFerieViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des jours fériés.

    ✅ PHASE 3: Permet de définir et gérer les jours fériés nationaux et locaux.
    Ces jours fériés sont utilisés pour :
    - Skipping de jours lors de la génération de récurrence
    - Affichage dans le calendrier de planification
    - Validation de disponibilité des équipes

    Permissions:
    - ADMIN: accès complet CRUD
    - Autres: lecture seule
    """
    queryset = JourFerie.objects.all()
    filterset_fields = ['date', 'type_ferie', 'actif', 'recurrent']
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        """Retourne le serializer approprié selon l'action."""
        if self.action == 'create':
            return JourFerieCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return JourFerieUpdateSerializer
        return JourFerieSerializer

    def get_permissions(self):
        """Permissions dynamiques : seul ADMIN peut créer/modifier/supprimer."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def dans_plage(self, request):
        """
        Retourne tous les jours fériés dans une plage de dates.

        Query params:
        - date_debut: Date de début (format: YYYY-MM-DD)
        - date_fin: Date de fin (format: YYYY-MM-DD)
        - actif_uniquement: true/false (default: true)
        """
        from datetime import datetime

        date_debut_str = request.query_params.get('date_debut')
        date_fin_str = request.query_params.get('date_fin')
        actif_uniquement = request.query_params.get('actif_uniquement', 'true').lower() == 'true'

        if not date_debut_str or not date_fin_str:
            return Response(
                {'error': 'Les paramètres date_debut et date_fin sont requis (format: YYYY-MM-DD).'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            date_debut = datetime.strptime(date_debut_str, '%Y-%m-%d').date()
            date_fin = datetime.strptime(date_fin_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Format de date invalide. Utilisez YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        jours_feries = JourFerie.get_jours_feries_dans_plage(
            date_debut=date_debut,
            date_fin=date_fin,
            actif_uniquement=actif_uniquement
        )

        serializer = JourFerieSerializer(jours_feries, many=True)
        return Response({
            'date_debut': date_debut_str,
            'date_fin': date_fin_str,
            'nombre_jours_feries': jours_feries.count(),
            'jours_feries': serializer.data
        })

    @action(detail=False, methods=['post'])
    def importer_feries_maroc(self, request):
        """
        ✅ PHASE 3: Importe automatiquement les jours fériés marocains pour une année donnée.

        Body:
        {
            "annee": 2024
        }
        """
        annee = request.data.get('annee')
        if not annee:
            return Response(
                {'error': 'Le paramètre "annee" est requis.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            annee = int(annee)
        except ValueError:
            return Response(
                {'error': 'L\'année doit être un nombre entier.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Jours fériés fixes au Maroc
        jours_feries_fixes = [
            {'nom': 'Jour de l\'An', 'mois': 1, 'jour': 1, 'type': 'NATIONAL'},
            {'nom': 'Manifeste de l\'Indépendance', 'mois': 1, 'jour': 11, 'type': 'NATIONAL'},
            {'nom': 'Fête du Travail', 'mois': 5, 'jour': 1, 'type': 'NATIONAL'},
            {'nom': 'Fête du Trône', 'mois': 7, 'jour': 30, 'type': 'NATIONAL'},
            {'nom': 'Révolution du Roi et du Peuple', 'mois': 8, 'jour': 20, 'type': 'NATIONAL'},
            {'nom': 'Fête de la Jeunesse', 'mois': 8, 'jour': 21, 'type': 'NATIONAL'},
            {'nom': 'Marche Verte', 'mois': 11, 'jour': 6, 'type': 'NATIONAL'},
            {'nom': 'Fête de l\'Indépendance', 'mois': 11, 'jour': 18, 'type': 'NATIONAL'},
        ]

        crees = []
        for ferie_data in jours_feries_fixes:
            from datetime import date
            date_ferie = date(annee, ferie_data['mois'], ferie_data['jour'])

            # Créer ou mettre à jour
            ferie, created = JourFerie.objects.get_or_create(
                date=date_ferie,
                type_ferie=ferie_data['type'],
                defaults={
                    'nom': ferie_data['nom'],
                    'recurrent': True,
                    'actif': True
                }
            )

            if created:
                crees.append(ferie)

        return Response({
            'message': f'{len(crees)} jours fériés importés pour l\'année {annee}.',
            'jours_feries_crees': JourFerieSerializer(crees, many=True).data
        }, status=status.HTTP_201_CREATED)


# ==============================================================================
# VUES ABSENCE
# ==============================================================================

class AbsenceViewSet(RoleBasedQuerySetMixin, RoleBasedPermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des absences (US 5.5.3).

    Implémente:
    - CRUD absences
    - Validation/refus
    - Impact sur les équipes

    Permissions (via RoleBasedPermissionMixin):
    - ADMIN: accès complet CRUD + validation
    - SUPERVISEUR: CRUD + validation sur les absences de ses opérateurs

    Le filtrage automatique est géré par RoleBasedQuerySetMixin.
    """
    queryset = Absence.objects.select_related(
        'operateur',
        'operateur__equipe',
        'operateur__equipe__site',
        'validee_par'
    ).all()
    filterset_class = AbsenceFilter

    # Permissions par action
    # SUPERVISEUR peut gérer les absences de ses opérateurs (via IsSuperviseurAndOwnsAbsence)
    permission_classes_by_action = {
        'create': [IsSuperviseurAndOwnsAbsence],
        'update': [IsSuperviseurAndOwnsAbsence],
        'partial_update': [IsSuperviseurAndOwnsAbsence],
        'destroy': [IsSuperviseurAndOwnsAbsence],
        'valider': [IsSuperviseurAndOwnsAbsence],
        'refuser': [IsSuperviseurAndOwnsAbsence],
        'annuler': [IsSuperviseurAndOwnsAbsence],
        'default': [IsAuthenticated],  # Lecture pour tous authentifiés (filtrage via mixin)
    }

    def get_serializer_class(self):
        if self.action == 'create':
            return AbsenceCreateSerializer
        return AbsenceSerializer

    def perform_create(self, serializer):
        serializer.save(_current_user=self.request.user)

    @action(detail=True, methods=['post'])
    def valider(self, request, pk=None):
        """Valide une absence. Permission: ADMIN only."""
        absence = self.get_object()

        if absence.statut != StatutAbsence.DEMANDEE:
            return Response(
                {'error': 'Seules les absences en attente peuvent être validées.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AbsenceValidationSerializer(data={'action': 'valider', **request.data})
        if serializer.is_valid():
            # Utiliser l'utilisateur connecté ou un admin par défaut
            user = request.user if request.user.is_authenticated else None
            absence = serializer.update_absence(absence, user, _current_user=request.user)
            return Response(AbsenceSerializer(absence).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def refuser(self, request, pk=None):
        """Refuse une absence. Permission: ADMIN only."""
        absence = self.get_object()

        if absence.statut != StatutAbsence.DEMANDEE:
            return Response(
                {'error': 'Seules les absences en attente peuvent être refusées.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AbsenceValidationSerializer(data={'action': 'refuser', **request.data})
        if serializer.is_valid():
            user = request.user if request.user.is_authenticated else None
            absence = serializer.update_absence(absence, user, _current_user=request.user)
            return Response(AbsenceSerializer(absence).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def annuler(self, request, pk=None):
        """Annule une absence. Permission: ADMIN only."""
        absence = self.get_object()

        if absence.statut not in [StatutAbsence.DEMANDEE, StatutAbsence.VALIDEE]:
            return Response(
                {'error': 'Cette absence ne peut pas être annulée.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        absence.statut = StatutAbsence.ANNULEE
        absence._current_user = request.user
        absence.save()
        return Response(AbsenceSerializer(absence).data)

    @action(detail=False, methods=['get'])
    def en_cours(self, request):
        """Liste les absences en cours (validées et actives aujourd'hui)."""
        today = timezone.now().date()
        absences = self.get_queryset().filter(
            statut=StatutAbsence.VALIDEE,
            date_debut__lte=today,
            date_fin__gte=today
        )
        serializer = AbsenceSerializer(absences, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def a_valider(self, request):
        """Liste les absences en attente de validation."""
        absences = self.get_queryset().filter(statut=StatutAbsence.DEMANDEE)
        serializer = AbsenceSerializer(absences, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def equipes_impactees(self, request):
        """Liste les équipes impactées par des absences aujourd'hui."""
        today = timezone.now().date()

        # Trouver les absences validées en cours
        absences_en_cours = Absence.objects.filter(
            statut=StatutAbsence.VALIDEE,
            date_debut__lte=today,
            date_fin__gte=today
        ).select_related('operateur__equipe')

        # Grouper par équipe
        equipes_data = {}
        for absence in absences_en_cours:
            if absence.operateur.equipe:
                equipe = absence.operateur.equipe
                if equipe.id not in equipes_data:
                    equipes_data[equipe.id] = {
                        'equipe': EquipeListSerializer(equipe).data,
                        'absences': []
                    }
                equipes_data[equipe.id]['absences'].append(AbsenceSerializer(absence).data)

        return Response(list(equipes_data.values()))


# ==============================================================================
# VUES HISTORIQUE RH
# ==============================================================================

class HistoriqueRHView(APIView):
    """
    Vue pour l'historique RH (US 5.5.4).

    Permet de consulter l'historique des affectations, absences et compétences.
    """

    def _get_equipes_gerees_ids(self, user):
        """Retourne les IDs des équipes que le superviseur gère."""
        try:
            superviseur = user.superviseur_profile
            return list(superviseur.equipes_gerees.filter(actif=True).values_list('id', flat=True))
        except AttributeError:  # Pas de profil superviseur
            return []

    def get(self, request):
        """
        Retourne l'historique RH filtré selon le rôle.
        """
        user = request.user
        roles = [ur.role.nom_role for ur in user.roles_utilisateur.all()]
        is_admin = 'ADMIN' in roles
        is_superviseur = 'SUPERVISEUR' in roles
        equipes_gerees_ids = self._get_equipes_gerees_ids(user) if is_superviseur else []

        operateur_id = request.query_params.get('operateur_id')
        equipe_id = request.query_params.get('equipe_id')
        date_debut = request.query_params.get('date_debut')
        date_fin = request.query_params.get('date_fin')
        type_historique = request.query_params.get('type', 'all')

        result = {}

        # Historique des équipes
        if type_historique in ['equipes', 'all']:
            hist_equipes = HistoriqueEquipeOperateur.objects.select_related(
                'operateur', 'equipe'
            )

            # Filtrage par rôle
            if not is_admin and is_superviseur:
                hist_equipes = hist_equipes.filter(equipe_id__in=equipes_gerees_ids)
            elif not is_admin:
                hist_equipes = hist_equipes.none()

            if operateur_id:
                hist_equipes = hist_equipes.filter(operateur_id=operateur_id)
            if equipe_id:
                hist_equipes = hist_equipes.filter(equipe_id=equipe_id)
            if date_debut:
                hist_equipes = hist_equipes.filter(date_debut__gte=date_debut)
            if date_fin:
                hist_equipes = hist_equipes.filter(
                    Q(date_fin__lte=date_fin) | Q(date_fin__isnull=True)
                )

            result['equipes'] = HistoriqueEquipeOperateurSerializer(
                hist_equipes, many=True
            ).data

        # Historique des absences
        if type_historique in ['absences', 'all']:
            absences = Absence.objects.select_related(
                'operateur', 'validee_par'
            )

            # Filtrage par rôle
            if not is_admin and is_superviseur:
                absences = absences.filter(operateur__equipe_id__in=equipes_gerees_ids)
            elif not is_admin:
                absences = absences.none()

            if operateur_id:
                absences = absences.filter(operateur_id=operateur_id)
            if date_debut:
                absences = absences.filter(date_debut__gte=date_debut)
            if date_fin:
                absences = absences.filter(date_fin__lte=date_fin)

            result['absences'] = AbsenceSerializer(absences, many=True).data

        # Historique des compétences
        if type_historique in ['competences', 'all']:
            competences = CompetenceOperateur.objects.select_related(
                'operateur', 'competence'
            )

            # Filtrage par rôle
            if not is_admin and is_superviseur:
                competences = competences.filter(operateur__equipe_id__in=equipes_gerees_ids)
            elif not is_admin:
                competences = competences.none()

            if operateur_id:
                competences = competences.filter(operateur_id=operateur_id)

            result['competences'] = CompetenceOperateurSerializer(
                competences, many=True
            ).data

        return Response(result)


# ==============================================================================
# VUE STATISTIQUES UTILISATEURS
# ==============================================================================

class StatistiquesUtilisateursView(APIView):
    """
    Vue pour les statistiques du module utilisateurs.

    Applique automatiquement le filtrage selon le rôle de l'utilisateur :
    - ADMIN : Toutes les statistiques
    - SUPERVISEUR : Statistiques de ses équipes/opérateurs/sites
    - CLIENT : Statistiques des équipes/opérateurs de ses sites (lecture seule)
    """

    def _get_filtered_querysets(self, user):
        """Applique le même filtrage que RoleBasedQuerySetMixin."""
        if not user or not user.is_authenticated:
            return {
                'Operateur': Operateur.objects.none(),
                'Equipe': Equipe.objects.none(),
                'Absence': Absence.objects.none(),
            }

        # ADMIN : Tout voir
        if user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return {
                'Operateur': Operateur.objects.all(),
                'Equipe': Equipe.objects.all(),
                'Absence': Absence.objects.all(),
            }

        # SUPERVISEUR : Filtre selon ses sites
        if user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists():
            if hasattr(user, 'superviseur_profile'):
                superviseur = user.superviseur_profile

                # Opérateurs : directs + équipes intervenant sur ses sites
                from api_planification.models import Tache

                equipes_ids = set()
                equipes_ids.update(superviseur.equipes_gerees.values_list('id', flat=True))

                taches_sur_mes_sites = Tache.objects.filter(
                    objets__site__superviseur=superviseur
                ).distinct()

                equipes_ids.update(taches_sur_mes_sites.values_list('equipes__id', flat=True))
                equipes_ids.update(
                    taches_sur_mes_sites.exclude(id_equipe__isnull=True).values_list('id_equipe', flat=True)
                )
                equipes_ids.discard(None)

                operateurs_qs = Operateur.objects.filter(
                    Q(superviseur=superviseur) | Q(equipe__id__in=equipes_ids)
                ).distinct()

                # ✅ Équipes : Utilise la nouvelle architecture multi-sites
                equipes_via_principal = Q(site_principal__superviseur=superviseur)
                equipes_via_secondaire = Q(sites_secondaires__superviseur=superviseur)
                equipes_legacy = Q(site__superviseur=superviseur)  # Legacy fallback
                equipes_qs = Equipe.objects.filter(
                    equipes_via_principal | equipes_via_secondaire | equipes_legacy | Q(id__in=equipes_ids)
                ).distinct()

                absences_qs = Absence.objects.filter(operateur__in=operateurs_qs)

                return {
                    'Operateur': operateurs_qs,
                    'Equipe': equipes_qs,
                    'Absence': absences_qs,
                }

        # CLIENT : Filtre selon ses sites (lecture seule, via structure_client)
        if user.roles_utilisateur.filter(role__nom_role='CLIENT').exists():
            if hasattr(user, 'client_profile'):
                client = user.client_profile

                # Vérifier que le client a une structure
                if not client.structure:
                    return {
                        'Operateur': Operateur.objects.none(),
                        'Equipe': Equipe.objects.none(),
                        'Absence': Absence.objects.none(),
                    }

                # ✅ Équipes travaillant sur ses sites (via structure_client)
                # Utilise la nouvelle architecture multi-sites (site_principal + sites_secondaires)
                equipes_via_principal = Q(site_principal__structure_client=client.structure)
                equipes_via_secondaire = Q(sites_secondaires__structure_client=client.structure)
                equipes_legacy = Q(site__structure_client=client.structure)  # Legacy fallback
                equipes_qs = Equipe.objects.filter(
                    equipes_via_principal | equipes_via_secondaire | equipes_legacy
                ).distinct()

                # ✅ Opérateurs des équipes de ses sites (via structure_client)
                # Utilise la nouvelle architecture multi-sites
                operateurs_via_principal = Q(equipe__site_principal__structure_client=client.structure)
                operateurs_via_secondaire = Q(equipe__sites_secondaires__structure_client=client.structure)
                operateurs_legacy = Q(equipe__site__structure_client=client.structure)  # Legacy fallback
                operateurs_qs = Operateur.objects.filter(
                    operateurs_via_principal | operateurs_via_secondaire | operateurs_legacy
                ).distinct()

                # ✅ Absences des opérateurs de ses équipes (via structure_client)
                # Utilise la nouvelle architecture multi-sites
                absences_via_principal = Q(operateur__equipe__site_principal__structure_client=client.structure)
                absences_via_secondaire = Q(operateur__equipe__sites_secondaires__structure_client=client.structure)
                absences_legacy = Q(operateur__equipe__site__structure_client=client.structure)  # Legacy fallback
                absences_qs = Absence.objects.filter(
                    absences_via_principal | absences_via_secondaire | absences_legacy
                ).distinct()

                return {
                    'Operateur': operateurs_qs,
                    'Equipe': equipes_qs,
                    'Absence': absences_qs,
                }

        # Autre rôle : Aucun accès
        return {
            'Operateur': Operateur.objects.none(),
            'Equipe': Equipe.objects.none(),
            'Absence': Absence.objects.none(),
        }

    def get(self, request):
        """Retourne les statistiques filtrées selon le rôle."""
        today = timezone.now().date()

        # Obtenir les querysets filtrés
        qs = self._get_filtered_querysets(request.user)

        # Statistiques utilisateurs (ADMIN uniquement)
        is_admin = request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists()
        stats_utilisateurs = {
            'total': Utilisateur.objects.count() if is_admin else 0,
            'actifs': Utilisateur.objects.filter(actif=True).count() if is_admin else 0,
        }

        # Statistiques opérateurs (filtrées)
        operateurs_actifs = qs['Operateur'].filter(statut='ACTIF')
        operateurs_disponibles = operateurs_actifs.exclude(
            absences__statut=StatutAbsence.VALIDEE,
            absences__date_debut__lte=today,
            absences__date_fin__gte=today
        ).distinct().count()

        stats_operateurs = {
            'total': qs['Operateur'].count(),
            'actifs': operateurs_actifs.count(),
            'disponibles_aujourdhui': operateurs_disponibles,
            'par_statut': dict(
                qs['Operateur'].values('statut')
                .annotate(count=Count('id'))
                .values_list('statut', 'count')
            ),
            'chefs_equipe': qs['Operateur'].filter(
                equipe_dirigee__actif=True
            ).distinct().count()
        }

        # Statistiques équipes (filtrées)
        # ⚡ OPTIMISÉ: Calcul des statuts opérationnels en SQL au lieu de N+1 queries
        equipes_actives = qs['Equipe'].filter(actif=True)
        equipes_count = equipes_actives.count()

        # Annoter les équipes avec le nombre de membres actifs et disponibles
        equipes_annotees = equipes_actives.annotate(
            nb_membres_actifs=Count(
                'operateurs',
                filter=Q(operateurs__statut='ACTIF')
            ),
            nb_membres_absents=Count(
                'operateurs',
                filter=Q(
                    operateurs__statut='ACTIF',
                    operateurs__absences__statut='VALIDEE',
                    operateurs__absences__date_debut__lte=today,
                    operateurs__absences__date_fin__gte=today
                )
            )
        ).values('nb_membres_actifs', 'nb_membres_absents')

        # Calculer les statuts en Python à partir des annotations
        completes = 0
        partielles = 0
        indisponibles = 0

        for eq in equipes_annotees:
            total = eq['nb_membres_actifs'] or 0
            absents = eq['nb_membres_absents'] or 0
            disponibles = total - absents

            if total == 0:
                indisponibles += 1
            elif disponibles == total:
                completes += 1
            elif disponibles > 0:
                partielles += 1
            else:
                indisponibles += 1

        stats_equipes = {
            'total': qs['Equipe'].count(),
            'actives': equipes_count,
            'statuts_operationnels': {
                'completes': completes,
                'partielles': partielles,
                'indisponibles': indisponibles,
            }
        }

        # Statistiques absences (filtrées)
        stats_absences = {
            'en_attente': qs['Absence'].filter(statut=StatutAbsence.DEMANDEE).count(),
            'en_cours': qs['Absence'].filter(
                statut=StatutAbsence.VALIDEE,
                date_debut__lte=today,
                date_fin__gte=today
            ).count(),
            'par_type': dict(
                qs['Absence'].filter(statut=StatutAbsence.VALIDEE)
                .values('type_absence')
                .annotate(count=Count('id'))
                .values_list('type_absence', 'count')
            )
        }

        return Response({
            'utilisateurs': stats_utilisateurs,
            'operateurs': stats_operateurs,
            'equipes': stats_equipes,
            'absences': stats_absences
        })
