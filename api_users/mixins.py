"""
Mixins pour le Filtrage Automatique par Rôle - GreenSIG

Ce module fournit des mixins réutilisables pour appliquer automatiquement
le filtrage des QuerySets en fonction du rôle de l'utilisateur.

Basé sur la matrice de permissions définie dans PERMISSIONS_MATRIX.md

Usage:
    class SiteViewSet(RoleBasedQuerySetMixin, viewsets.ModelViewSet):
        queryset = Site.objects.all()
        role_filter_field = 'site'  # Optionnel, par défaut détecté automatiquement
"""

from django.db.models import Q


class RoleBasedQuerySetMixin:
    """
    Mixin pour filtrer automatiquement les QuerySets selon le rôle de l'utilisateur.

    Ce mixin applique les règles de filtrage définies dans la matrice de permissions :
    - ADMIN : Voit tout (pas de filtre)
    - SUPERVISEUR : Voit uniquement les ressources liées à ses équipes
    - CLIENT : Voit uniquement ses ressources

    Le mixin détecte automatiquement le type de modèle et applique le bon filtre.
    """

    def get_queryset(self):
        """
        Filtre le queryset en fonction du rôle de l'utilisateur.

        Returns:
            QuerySet filtré selon le rôle
        """
        queryset = super().get_queryset()
        user = self.request.user

        if not user or not user.is_authenticated:
            return queryset.none()

        # ADMIN : Aucun filtre, voit tout
        if user.roles_utilisateur.filter(role__nom_role='ADMIN').exists():
            return queryset

        # SUPERVISEUR : Filtrage selon le type de ressource
        if user.roles_utilisateur.filter(role__nom_role='SUPERVISEUR').exists():
            if hasattr(user, 'superviseur_profile'):
                return self._filter_for_superviseur(queryset, user.superviseur_profile)

        # CLIENT : Filtrage selon le type de ressource
        if user.roles_utilisateur.filter(role__nom_role='CLIENT').exists():
            if hasattr(user, 'client_profile'):
                return self._filter_for_client(queryset, user.client_profile)

        # Par défaut, aucun accès
        return queryset.none()

    def _filter_for_superviseur(self, queryset, superviseur):
        """
        Filtre le queryset pour un superviseur.

        Args:
            queryset: QuerySet à filtrer
            superviseur: Profil Superviseur de l'utilisateur

        Returns:
            QuerySet filtré
        """
        model_name = queryset.model.__name__

        # Sites : Sites affectés directement au superviseur
        if model_name == 'Site':
            return queryset.filter(superviseur=superviseur)

        # SousSite : Sous-sites des sites affectés au superviseur
        if model_name == 'SousSite':
            return queryset.filter(site__superviseur=superviseur)

        # Opérateurs : Ses opérateurs
        if model_name == 'Operateur':
            return queryset.filter(superviseur=superviseur)

        # Équipes : Ses équipes
        if model_name == 'Equipe':
            return queryset.filter(superviseur=superviseur)

        # Absences : Absences de ses opérateurs
        if model_name == 'Absence':
            return queryset.filter(operateur__superviseur=superviseur)

        # Tâches : Tâches assignées à ses équipes
        if model_name == 'Tache':
            return queryset.filter(equipes__superviseur=superviseur).distinct()

        # Réclamations : Réclamations sur les sites affectés au superviseur
        if model_name == 'Reclamation':
            return queryset.filter(site__superviseur=superviseur)

        # Objets GIS (15 types) : Objets sur les sites affectés au superviseur
        # Tous les objets GIS ont un champ 'site'
        if hasattr(queryset.model, 'site'):
            return queryset.filter(site__superviseur=superviseur)

        # Par défaut, retourner le queryset complet (au cas où)
        return queryset

    def _filter_for_client(self, queryset, client):
        """
        Filtre le queryset pour un client.

        Args:
            queryset: QuerySet à filtrer
            client: Profil Client de l'utilisateur

        Returns:
            QuerySet filtré
        """
        model_name = queryset.model.__name__

        # Sites : Uniquement ses sites
        if model_name == 'Site':
            return queryset.filter(client=client)

        # SousSite : Sous-sites de ses sites
        if model_name == 'SousSite':
            return queryset.filter(site__client=client)

        # Tâches : Tâches du client (lecture seule)
        if model_name == 'Tache':
            return queryset.filter(id_client=client)

        # Réclamations : Ses réclamations
        if model_name == 'Reclamation':
            return queryset.filter(site__client=client)

        # Objets GIS (15 types) : Objets sur ses sites
        # Tous les objets GIS ont un champ 'site'
        if hasattr(queryset.model, 'site'):
            return queryset.filter(site__client=client)

        # Client : Son profil uniquement
        if model_name == 'Client':
            return queryset.filter(pk=client.pk)

        # Autres ressources : Aucun accès
        return queryset.none()


class RoleBasedPermissionMixin:
    """
    Mixin pour gérer les permissions par méthode HTTP.

    Ce mixin permet de définir des permissions différentes selon l'action.

    Usage:
        class EquipeViewSet(RoleBasedPermissionMixin, viewsets.ModelViewSet):
            permission_classes_by_action = {
                'create': [IsAdmin],
                'update': [IsAdmin | IsSuperviseurAndOwnsEquipe],
                'destroy': [IsAdmin],
                'default': [IsAuthenticated],
            }
    """

    permission_classes_by_action = {}

    def get_permissions(self):
        """
        Retourne les permissions selon l'action.

        Returns:
            Liste des instances de permissions
        """
        try:
            # Récupérer les permissions pour cette action
            permission_classes = self.permission_classes_by_action.get(
                self.action,
                self.permission_classes_by_action.get('default', self.permission_classes)
            )
            return [permission() for permission in permission_classes]
        except (AttributeError, KeyError):
            # Fallback sur les permissions par défaut
            return super().get_permissions()


class SoftDeleteMixin:
    """
    Mixin pour la suppression douce (soft delete).

    Au lieu de supprimer définitivement, marque l'objet comme supprimé.

    Le modèle doit avoir un champ 'deleted_at' (DateTimeField, null=True).

    Usage:
        class TacheViewSet(SoftDeleteMixin, viewsets.ModelViewSet):
            queryset = Tache.objects.all()
    """

    def perform_destroy(self, instance):
        """
        Effectue une suppression douce au lieu de supprimer définitivement.

        Args:
            instance: Instance à supprimer
        """
        if hasattr(instance, 'deleted_at'):
            from django.utils import timezone
            instance.deleted_at = timezone.now()
            instance.save(update_fields=['deleted_at'])
        else:
            # Si le modèle n'a pas de champ deleted_at, suppression normale
            super().perform_destroy(instance)

    def get_queryset(self):
        """
        Exclut les objets supprimés du queryset.

        Returns:
            QuerySet sans les objets supprimés
        """
        queryset = super().get_queryset()

        # Exclure les objets marqués comme supprimés
        if hasattr(queryset.model, 'deleted_at'):
            queryset = queryset.filter(deleted_at__isnull=True)

        return queryset


class AuditMixin:
    """
    Mixin pour tracer les actions de création/modification.

    Enregistre automatiquement l'utilisateur qui a créé/modifié l'objet.

    Le modèle doit avoir les champs :
    - created_by (ForeignKey vers Utilisateur, null=True)
    - updated_by (ForeignKey vers Utilisateur, null=True)

    Usage:
        class SiteViewSet(AuditMixin, viewsets.ModelViewSet):
            queryset = Site.objects.all()
    """

    def perform_create(self, serializer):
        """
        Enregistre l'utilisateur qui crée l'objet.

        Args:
            serializer: Serializer contenant les données
        """
        if hasattr(serializer.Meta.model, 'created_by'):
            serializer.save(created_by=self.request.user)
        else:
            super().perform_create(serializer)

    def perform_update(self, serializer):
        """
        Enregistre l'utilisateur qui modifie l'objet.

        Args:
            serializer: Serializer contenant les données
        """
        if hasattr(serializer.Meta.model, 'updated_by'):
            serializer.save(updated_by=self.request.user)
        else:
            super().perform_update(serializer)


class ExportMixin:
    """
    Mixin pour ajouter des fonctionnalités d'export (CSV, Excel, PDF).

    Respecte automatiquement les filtres de rôle.

    Usage:
        class SiteViewSet(ExportMixin, RoleBasedQuerySetMixin, viewsets.ModelViewSet):
            queryset = Site.objects.all()
            export_fields = ['nom_site', 'code_site', 'superficie']  # Optionnel
    """

    export_fields = None  # Définir les champs à exporter, ou None pour tous

    def get_export_queryset(self):
        """
        Retourne le queryset pour l'export.

        Respecte les filtres de rôle via RoleBasedQuerySetMixin.

        Returns:
            QuerySet filtré pour l'export
        """
        return self.filter_queryset(self.get_queryset())

    def get_export_fields(self):
        """
        Retourne la liste des champs à exporter.

        Returns:
            Liste des noms de champs
        """
        if self.export_fields:
            return self.export_fields

        # Par défaut, tous les champs du modèle (sauf relations)
        model = self.queryset.model
        return [f.name for f in model._meta.fields if not f.is_relation]
