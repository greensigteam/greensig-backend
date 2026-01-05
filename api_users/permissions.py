"""
Système de Permissions Unifié - GreenSIG

Ce module définit toutes les permissions réutilisables du système.
Basé sur la matrice de permissions définie dans PERMISSIONS_MATRIX.md

Rôles :
- ADMIN : Accès complet
- SUPERVISEUR : Accès filtré à ses équipes et sites
- CLIENT : Accès filtré à ses sites uniquement
"""

from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Permission : Utilisateur est ADMIN.

    ADMIN a accès complet à toutes les ressources.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Vérifier si l'utilisateur a le rôle ADMIN
        return request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists()


class IsSuperviseur(permissions.BasePermission):
    """
    Permission : Utilisateur est SUPERVISEUR.

    SUPERVISEUR a accès filtré à ses équipes et sites liés.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Vérifier si l'utilisateur a le rôle SUPERVISEUR
        return request.user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists()


class IsClient(permissions.BasePermission):
    """
    Permission : Utilisateur est CLIENT.

    CLIENT a accès en lecture seule à ses sites uniquement.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Vérifier si l'utilisateur a le rôle CLIENT
        return request.user.roles_utilisateur.filter(role__nom_role='CLIENT').exists()


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permission : ADMIN peut tout faire, les autres en lecture seule.

    Utilisé pour les ressources système (rôles, compétences, etc.)
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Lecture seule pour tous
        if request.method in permissions.SAFE_METHODS:
            return True

        # Modification uniquement pour ADMIN
        return request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists()


class IsSuperviseurAndOwnsOperateur(permissions.BasePermission):
    """
    Permission : SUPERVISEUR peut gérer ses opérateurs.

    Vérifie que l'opérateur appartient bien au superviseur.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # SUPERVISEUR peut gérer ses opérateurs
        if request.user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists():
            if hasattr(request.user, 'superviseur_profile'):
                return obj.superviseur == request.user.superviseur_profile

        return False


class IsSuperviseurAndOwnsEquipe(permissions.BasePermission):
    """
    Permission : SUPERVISEUR peut gérer ses équipes.

    Vérifie que l'équipe appartient bien au superviseur.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # SUPERVISEUR peut gérer ses équipes
        if request.user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists():
            if hasattr(request.user, 'superviseur_profile'):
                return obj.superviseur == request.user.superviseur_profile

        return False


class IsSuperviseurAndOwnsSite(permissions.BasePermission):
    """
    Permission : SUPERVISEUR peut gérer les sites liés à ses équipes.

    Vérifie que le site a des tâches assignées aux équipes du superviseur.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # SUPERVISEUR peut voir les sites de ses équipes
        if request.user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists():
            if hasattr(request.user, 'superviseur_profile'):
                # Vérifier si ce site a des tâches assignées aux équipes du superviseur
                from api_planification.models import Tache
                return Tache.objects.filter(
                    site=obj,
                    equipes__site__superviseur=request.user.superviseur_profile
                ).exists()

        return False


class IsClientAndOwnsSite(permissions.BasePermission):
    """
    Permission : CLIENT peut voir uniquement les sites de sa structure.

    Vérifie que le site appartient bien à la structure du client.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # CLIENT peut voir uniquement les sites de sa structure
        if request.user.roles_utilisateur.filter(role__nom_role='CLIENT').exists():
            if hasattr(request.user, 'client_profile'):
                client_profile = request.user.client_profile
                if client_profile.structure:
                    return obj.structure_client == client_profile.structure
                # Fallback legacy : vérifier l'ancien champ client
                return obj.client == client_profile

        return False


class IsClientOfStructure(permissions.BasePermission):
    """
    Permission : CLIENT peut accéder uniquement aux ressources de sa structure.

    Vérifie que l'objet appartient à la structure du client connecté.
    Fonctionne pour Site, Tache, Reclamation qui ont un champ structure_client.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # CLIENT peut accéder aux ressources de sa structure uniquement
        if request.user.roles_utilisateur.filter(role__nom_role='CLIENT').exists():
            if hasattr(request.user, 'client_profile'):
                client_structure = request.user.client_profile.structure
                if client_structure:
                    # L'objet peut avoir structure_client directement
                    if hasattr(obj, 'structure_client'):
                        return obj.structure_client == client_structure
                    # Ou via site.structure_client
                    if hasattr(obj, 'site') and obj.site:
                        return obj.site.structure_client == client_structure

        return False


class CanCreateReclamation(permissions.BasePermission):
    """
    Permission : Tous les utilisateurs authentifiés peuvent créer des réclamations.

    ADMIN, SUPERVISEUR, CLIENT peuvent créer des réclamations.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Création autorisée pour tous
        if request.method == 'POST':
            return True

        # Lecture selon les permissions habituelles
        return True


class CanManageReclamation(permissions.BasePermission):
    """
    Permission : ADMIN et SUPERVISEUR peuvent traiter/clôturer les réclamations.

    CLIENT peut uniquement créer et lire ses réclamations.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # SUPERVISEUR peut gérer les réclamations de ses sites
        if request.user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists():
            if hasattr(request.user, 'superviseur_profile'):
                # Vérifier si le site de la réclamation est géré par le superviseur
                from api_planification.models import Tache
                return Tache.objects.filter(
                    site=obj.site,
                    equipes__site__superviseur=request.user.superviseur_profile
                ).exists()

        # CLIENT peut lire uniquement les réclamations de sa structure
        if request.user.roles_utilisateur.filter(role__nom_role='CLIENT').exists():
            if hasattr(request.user, 'client_profile'):
                # Lecture seule
                if request.method in permissions.SAFE_METHODS:
                    client_structure = request.user.client_profile.structure
                    if client_structure:
                        # Vérifier via structure_client directement ou via site
                        if obj.structure_client:
                            return obj.structure_client == client_structure
                        if obj.site and obj.site.structure_client:
                            return obj.site.structure_client == client_structure
                    # Fallback legacy
                    if obj.site and obj.site.client:
                        return obj.site.client == request.user.client_profile

        return False


class IsSelfOrAdmin(permissions.BasePermission):
    """
    Permission : Utilisateur peut modifier son propre profil, ou être ADMIN.

    Utilisé pour les endpoints de profil utilisateur.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # L'utilisateur peut modifier son propre profil
        return obj == request.user


class CanExportData(permissions.BasePermission):
    """
    Permission : ADMIN, SUPERVISEUR, CLIENT peuvent exporter leurs données.

    Les données sont automatiquement filtrées selon le rôle.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Tous les rôles authentifiés peuvent exporter
        return request.user.roles_utilisateur.exists()


class CanImportData(permissions.BasePermission):
    """
    Permission : ADMIN et SUPERVISEUR peuvent importer des données.

    CLIENT ne peut pas importer.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN et SUPERVISEUR peuvent importer
        return request.user.roles_utilisateur.filter(
            role__nom_role__in=['ADMIN', 'SUPERVISEUR']
        ).exists()


class IsSuperviseurAndOwnsAbsence(permissions.BasePermission):
    """
    Permission : SUPERVISEUR peut gérer les absences de ses opérateurs.

    Vérifie que l'opérateur de l'absence est supervisé par l'utilisateur.
    Un opérateur est sous un superviseur si:
    - operateur.superviseur == superviseur (relation directe)
    - operateur.equipe.site.superviseur == superviseur (via équipe/site)
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # SUPERVISEUR peut créer des absences pour ses opérateurs
        if request.user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists():
            if hasattr(request.user, 'superviseur_profile'):
                return True

        return False

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN peut tout
        if request.user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return True

        # SUPERVISEUR peut gérer les absences de ses opérateurs
        if request.user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists():
            if hasattr(request.user, 'superviseur_profile'):
                superviseur = request.user.superviseur_profile
                operateur = obj.operateur

                # Vérifier relation directe
                if operateur.superviseur == superviseur:
                    return True

                # Vérifier via équipe -> site -> superviseur
                if operateur.equipe and operateur.equipe.site:
                    if operateur.equipe.site.superviseur == superviseur:
                        return True

        return False
