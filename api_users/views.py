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
    Utilisateur, Role, UtilisateurRole, Client, Superviseur, Operateur,
    Competence, CompetenceOperateur, Equipe, Absence,
    HistoriqueEquipeOperateur, StatutAbsence, StatutOperateur, NiveauCompetence
)
from .serializers import (
    UtilisateurSerializer, UtilisateurCreateSerializer, UtilisateurUpdateSerializer,
    ChangePasswordSerializer, RoleSerializer, UtilisateurRoleSerializer,
    ClientSerializer, ClientCreateSerializer,
    SuperviseurSerializer, SuperviseurCreateSerializer,
    CompetenceSerializer, CompetenceOperateurSerializer, CompetenceOperateurUpdateSerializer,
    OperateurListSerializer, OperateurDetailSerializer,
    OperateurCreateSerializer, OperateurUpdateSerializer,
    EquipeListSerializer, EquipeDetailSerializer,
    EquipeCreateSerializer, EquipeUpdateSerializer, AffecterMembresSerializer,
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
    IsAdminOrReadOnly, IsSelfOrAdmin
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
    """
    permission_classes = [IsAdmin]

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
            return Response({'message': f'Rôle {role.nom_role} retiré avec succès.'})
        except UtilisateurRole.DoesNotExist:
            return Response({'error': 'L’utilisateur ne possède pas ce rôle.'}, status=status.HTTP_400_BAD_REQUEST)
    queryset = Utilisateur.objects.all().order_by('nom', 'prenom')
    filterset_class = UtilisateurFilter

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
# VUES CLIENT
# ==============================================================================

class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des clients.

    Gère le CRUD complet des clients avec leur profil utilisateur associé.

    Permissions:
    - ADMIN: accès complet CRUD
    - CLIENT: lecture seule sur son propre profil (filtré par get_queryset)
    """
    permission_classes = [IsAuthenticated]
    queryset = Client.objects.select_related('utilisateur').prefetch_related(
        'utilisateur__roles_utilisateur__role'
    ).all()

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

        # Récupérer tous les sites du client
        sites = Site.objects.filter(client=client).prefetch_related('objets')

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

    def destroy(self, request, *args, **kwargs):
        """Soft delete : désactive l'utilisateur superviseur."""
        instance = self.get_object()
        instance.utilisateur.actif = False
        instance.utilisateur.save()
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
    queryset = Operateur.objects.select_related(
        'superviseur__utilisateur', 'equipe'
    ).prefetch_related('competences_operateur__competence').all()
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

        return Response(
            {'message': 'Opérateur désactivé avec succès.'},
            status=status.HTTP_200_OK
        )

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
        """Liste les opérateurs pouvant être chef d'équipe."""
        operateurs = self.get_queryset().filter(
            statut='ACTIF',
            competences_operateur__competence__nom_competence="Gestion d'équipe",
            competences_operateur__niveau__in=[
                NiveauCompetence.INTERMEDIAIRE,
                NiveauCompetence.EXPERT,
            ]
        ).distinct()

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
    queryset = Equipe.objects.select_related(
        'chef_equipe', 'site__superviseur__utilisateur'
    ).prefetch_related(
        Prefetch('operateurs', queryset=Operateur.objects.filter(statut=StatutOperateur.ACTIF))
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
        """Override pour debug et s'assurer que le filtrage django-filter est appliqué."""
        import logging
        logger = logging.getLogger(__name__)

        # Log avant filtrage
        logger.info(f"[EquipeViewSet] AVANT filtrage: {queryset.count()} équipes")
        logger.info(f"[EquipeViewSet] Query params: {self.request.query_params}")

        # Appliquer le filtrage (django-filter + autres)
        filtered = super().filter_queryset(queryset)

        # Log après filtrage
        logger.info(f"[EquipeViewSet] APRÈS filtrage: {filtered.count()} équipes")

        return filtered

    def get_serializer_class(self):
        if self.action == 'create':
            return EquipeCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return EquipeUpdateSerializer
        elif self.action == 'retrieve':
            return EquipeDetailSerializer
        return EquipeListSerializer

    def destroy(self, request, *args, **kwargs):
        """Désactive une équipe au lieu de la supprimer. Permission: ADMIN only."""
        instance = self.get_object()
        instance.actif = False
        instance.save()
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
    - SUPERVISEUR: lecture seule sur les absences de ses opérateurs

    Le filtrage automatique est géré par RoleBasedQuerySetMixin.
    """
    queryset = Absence.objects.select_related(
        'operateur',
        'operateur__equipe',
        'validee_par'
    ).all()
    filterset_class = AbsenceFilter

    # Permissions par action
    permission_classes_by_action = {
        'create': [IsAdmin],
        'update': [IsAdmin],
        'partial_update': [IsAdmin],
        'destroy': [IsAdmin],
        'valider': [IsAdmin],
        'refuser': [IsAdmin],
        'annuler': [IsAdmin],
        'default': [IsAuthenticated],  # Lecture pour tous authentifiés (filtrage via mixin)
    }

    def get_serializer_class(self):
        if self.action == 'create':
            return AbsenceCreateSerializer
        return AbsenceSerializer

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
            absence = serializer.update_absence(absence, user)
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
            absence = serializer.update_absence(absence, user)
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
    """Vue pour les statistiques du module utilisateurs."""

    def get(self, request):
        """Retourne les statistiques globales."""
        today = timezone.now().date()

        # Statistiques utilisateurs
        stats_utilisateurs = {
            'total': Utilisateur.objects.count(),
            'actifs': Utilisateur.objects.filter(actif=True).count(),
                # 'par_type': dict(
                #     Utilisateur.objects.values('type_utilisateur')
                #     .annotate(count=Count('id'))
                #     .values_list('type_utilisateur', 'count')
                # )
        }

        # Statistiques opérateurs
        operateurs_actifs = Operateur.objects.filter(statut='ACTIF')
        operateurs_disponibles = operateurs_actifs.exclude(
            absences__statut=StatutAbsence.VALIDEE,
            absences__date_debut__lte=today,
            absences__date_fin__gte=today
        ).distinct().count()

        stats_operateurs = {
            'total': Operateur.objects.count(),
            'actifs': operateurs_actifs.count(),
            'disponibles_aujourdhui': operateurs_disponibles,
            'par_statut': dict(
                Operateur.objects.values('statut')
                .annotate(count=Count('id'))
                .values_list('statut', 'count')
            ),
            'chefs_equipe': Operateur.objects.filter(
                equipe_dirigee__actif=True
            ).distinct().count()
        }

        # Statistiques équipes
        equipes_actives = Equipe.objects.filter(actif=True)
        stats_equipes = {
            'total': Equipe.objects.count(),
            'actives': equipes_actives.count(),
            'statuts_operationnels': {
                'completes': sum(1 for e in equipes_actives if e.statut_operationnel == 'COMPLETE'),
                'partielles': sum(1 for e in equipes_actives if e.statut_operationnel == 'PARTIELLE'),
                'indisponibles': sum(1 for e in equipes_actives if e.statut_operationnel == 'INDISPONIBLE'),
            }
        }

        # Statistiques absences
        stats_absences = {
            'en_attente': Absence.objects.filter(statut=StatutAbsence.DEMANDEE).count(),
            'en_cours': Absence.objects.filter(
                statut=StatutAbsence.VALIDEE,
                date_debut__lte=today,
                date_fin__gte=today
            ).count(),
            'par_type': dict(
                Absence.objects.filter(statut=StatutAbsence.VALIDEE)
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
