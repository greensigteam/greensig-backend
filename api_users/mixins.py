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

import logging
from django.db.models import Q

logger = logging.getLogger(__name__)


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
        model_name = queryset.model.__name__

        if not user or not user.is_authenticated:
            logger.debug(f"[RoleBasedQuerySetMixin] {model_name}: Utilisateur non authentifié")
            return queryset.none()

        # Récupérer tous les rôles de l'utilisateur
        roles = list(user.roles_utilisateur.values_list('role__nom_role', flat=True))
        logger.info(f"[RoleBasedQuerySetMixin] {model_name}: User={user.email}, Roles={roles}")

        # ADMIN : Aucun filtre, voit tout
        if 'ADMIN' in roles:
            logger.info(f"[RoleBasedQuerySetMixin] {model_name}: ADMIN → pas de filtrage")
            return queryset

        # SUPERVISEUR : Filtrage selon le type de ressource
        if 'SUPERVISEUR' in roles:
            has_profile = hasattr(user, 'superviseur_profile')
            logger.info(f"[RoleBasedQuerySetMixin] {model_name}: SUPERVISEUR, has_profile={has_profile}")
            if has_profile:
                try:
                    superviseur = user.superviseur_profile
                    logger.info(f"[RoleBasedQuerySetMixin] {model_name}: Superviseur ID={superviseur.utilisateur_id}")
                    result = self._filter_for_superviseur(queryset, superviseur)
                    logger.info(f"[RoleBasedQuerySetMixin] {model_name}: Après filtrage SUPERVISEUR: {result.count()} résultats")
                    return result
                except Exception as e:
                    logger.error(f"[RoleBasedQuerySetMixin] {model_name}: Erreur profil superviseur: {e}")
            else:
                logger.warning(f"[RoleBasedQuerySetMixin] {model_name}: SUPERVISEUR sans profil superviseur_profile!")

        # CLIENT : Filtrage selon le type de ressource
        if 'CLIENT' in roles:
            has_profile = hasattr(user, 'client_profile')
            logger.info(f"[RoleBasedQuerySetMixin] {model_name}: CLIENT, has_profile={has_profile}")
            if has_profile:
                try:
                    client = user.client_profile
                    result = self._filter_for_client(queryset, client)
                    logger.info(f"[RoleBasedQuerySetMixin] {model_name}: Après filtrage CLIENT: {result.count()} résultats")
                    return result
                except Exception as e:
                    logger.error(f"[RoleBasedQuerySetMixin] {model_name}: Erreur profil client: {e}")

        # Par défaut, aucun accès
        logger.warning(f"[RoleBasedQuerySetMixin] {model_name}: Aucun rôle valide → queryset.none()")
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

        # Opérateurs : Ses opérateurs + opérateurs des équipes sur ses sites
        if model_name == 'Operateur':
            # 1. Opérateurs directement supervisés (relation directe)
            operateurs_directs = Q(superviseur=superviseur)

            # 2. Opérateurs des équipes affectées aux sites du superviseur
            operateurs_via_equipe_site = Q(equipe__site__superviseur=superviseur)

            # 3. Opérateurs des équipes avec tâches sur les sites du superviseur
            from api_planification.models import Tache

            taches_sur_mes_sites = Tache.objects.filter(
                deleted_at__isnull=True,
                objets__site__superviseur=superviseur
            ).distinct()

            equipes_ids_avec_taches = set()
            # M2M relation
            equipes_ids_avec_taches.update(
                taches_sur_mes_sites.values_list('equipes__id', flat=True)
            )
            # Legacy FK
            equipes_ids_avec_taches.update(
                taches_sur_mes_sites.exclude(id_equipe__isnull=True).values_list('id_equipe', flat=True)
            )
            equipes_ids_avec_taches.discard(None)

            operateurs_via_taches = Q(equipe__id__in=equipes_ids_avec_taches) if equipes_ids_avec_taches else Q(pk__in=[])

            # Combiner avec OR
            return queryset.filter(operateurs_directs | operateurs_via_equipe_site | operateurs_via_taches).distinct()

        # Équipes : Ses équipes + équipes avec tâches sur ses sites
        if model_name == 'Equipe':
            # 1. Équipes affectées à ses sites
            equipes_affectees = Q(site__superviseur=superviseur)

            # 2. Équipes ayant des tâches sur les sites du superviseur
            # Via Tache.equipes (M2M) ou Tache.id_equipe (legacy)
            from api_planification.models import Tache
            sites_superviseur_ids = superviseur.equipes_gerees.values_list('site_id', flat=True).distinct()

            taches_sur_mes_sites = Tache.objects.filter(
                deleted_at__isnull=True,
                objets__site__superviseur=superviseur
            ).distinct()

            equipes_ids_avec_taches = set()
            # M2M relation (multi-équipes)
            equipes_ids_avec_taches.update(
                taches_sur_mes_sites.values_list('equipes__id', flat=True)
            )
            # Legacy FK relation
            equipes_ids_avec_taches.update(
                taches_sur_mes_sites.exclude(id_equipe__isnull=True).values_list('id_equipe', flat=True)
            )
            equipes_ids_avec_taches.discard(None)  # Retirer None

            equipes_avec_taches = Q(id__in=equipes_ids_avec_taches)

            # Combiner les deux critères avec OR
            return queryset.filter(equipes_affectees | equipes_avec_taches).distinct()

        # Absences : Absences de ses opérateurs
        # Un opérateur est "sous" un superviseur si:
        # 1. operateur.superviseur == superviseur (relation directe)
        # 2. operateur.equipe.site.superviseur == superviseur (via équipe/site)
        if model_name == 'Absence':
            # Relation directe
            absences_direct = Q(operateur__superviseur=superviseur)
            # Via équipe -> site -> superviseur
            absences_via_equipe = Q(operateur__equipe__site__superviseur=superviseur)
            return queryset.filter(absences_direct | absences_via_equipe).distinct()

        # Tâches : Tâches assignées à ses équipes OU tâches sur ses sites sans équipe
        if model_name == 'Tache':
            # Tâches avec objets sur les sites du superviseur
            # Cela inclut automatiquement les tâches avec ou sans équipe
            return queryset.filter(
                objets__site__superviseur=superviseur
            ).distinct()

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

        # Vérifier que le client a une structure assignée
        if not client.structure:
            # Pas de structure = pas d'accès (sauf son propre profil)
            if model_name == 'Client':
                return queryset.filter(pk=client.pk)
            if model_name == 'Competence':
                return queryset.all()  # Compétences accessibles à tous
            return queryset.none()

        # Sites : Uniquement ses sites (via structure_client)
        if model_name == 'Site':
            return queryset.filter(structure_client=client.structure)

        # SousSite : Sous-sites de ses sites (via structure_client)
        if model_name == 'SousSite':
            return queryset.filter(site__structure_client=client.structure)

        # Tâches : Tâches du client (lecture seule, via id_structure_client)
        if model_name == 'Tache':
            return queryset.filter(id_structure_client=client.structure)

        # Réclamations : Ses réclamations (via structure_client)
        if model_name == 'Reclamation':
            return queryset.filter(structure_client=client.structure)

        # Équipes : Équipes travaillant sur ses sites (via structure_client)
        if model_name == 'Equipe':
            return queryset.filter(site__structure_client=client.structure)

        # Opérateurs : Opérateurs des équipes travaillant sur ses sites (via structure_client)
        if model_name == 'Operateur':
            from api_planification.models import Tache

            # 1. Opérateurs dont l'équipe est affectée aux sites du client
            equipes_affectees_ids = set()
            from api.models import Site
            sites_client = Site.objects.filter(structure_client=client.structure)
            equipes_affectees_ids.update(
                sites_client.values_list('equipes_affectees__id', flat=True)
            )

            # 2. Opérateurs dont l'équipe a des tâches sur les sites du client
            taches_sur_sites_client = Tache.objects.filter(
                deleted_at__isnull=True,
                objets__site__structure_client=client.structure
            ).distinct()

            # M2M relation
            equipes_ids_avec_taches = set()
            equipes_ids_avec_taches.update(
                taches_sur_sites_client.values_list('equipes__id', flat=True)
            )
            # Legacy FK
            equipes_ids_avec_taches.update(
                taches_sur_sites_client.exclude(id_equipe__isnull=True).values_list('id_equipe', flat=True)
            )

            # Combiner tous les IDs d'équipes
            all_equipes_ids = equipes_affectees_ids | equipes_ids_avec_taches
            all_equipes_ids.discard(None)

            if not all_equipes_ids:
                return queryset.none()

            return queryset.filter(equipe__id__in=all_equipes_ids).distinct()

        # Absences : Absences des opérateurs de ses équipes (via structure_client)
        if model_name == 'Absence':
            return queryset.filter(operateur__equipe__site__structure_client=client.structure)

        # Compétences : Toutes les compétences (référentiel, lecture seule)
        if model_name == 'Competence':
            return queryset.all()

        # Objets GIS (15 types) : Objets sur ses sites (via structure_client)
        # Tous les objets GIS ont un champ 'site'
        if hasattr(queryset.model, 'site'):
            return queryset.filter(site__structure_client=client.structure)

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
