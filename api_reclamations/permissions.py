from rest_framework import permissions


class IsReclamationCreatorOrTeamReader(permissions.BasePermission):
    """
    Permission pour les évaluations de satisfaction avec retour d'expérience.

    Règles:
    - **Lecture (GET)**:
      * Le créateur de la réclamation
      * Le superviseur de l'équipe affectée (retour d'expérience)
      * Les ADMIN/Staff (supervision générale)

    - **Création/Modification/Suppression (POST/PUT/PATCH/DELETE)**:
      * SEUL le créateur de la réclamation

    Tous les niveaux d'utilisateurs peuvent créer des réclamations,
    mais seul le créateur peut l'évaluer. Les traiteurs peuvent consulter
    l'évaluation pour le retour d'expérience.
    """

    def has_permission(self, request, view):
        # L'utilisateur doit être authentifié
        if not request.user or not request.user.is_authenticated:
            return False

        # Pour la création (POST), on vérifiera dans le create() du ViewSet
        # que l'utilisateur est bien le créateur de la réclamation
        return True

    def has_object_permission(self, request, view, obj):
        """
        Vérifie les permissions au niveau objet.

        Args:
            obj: Instance de SatisfactionClient
        """
        user = request.user
        reclamation = obj.reclamation

        # Lecture (GET): créateur + superviseur de l'équipe + ADMIN
        if request.method in permissions.SAFE_METHODS:
            # Le créateur peut lire
            if reclamation.createur == user:
                return True

            # Les ADMIN/Staff peuvent lire (supervision générale)
            if user.is_staff or user.is_superuser:
                return True

            # Le superviseur de l'équipe affectée peut lire (retour d'expérience)
            if reclamation.equipe_affectee:
                if hasattr(user, 'superviseur_profile'):
                    superviseur = user.superviseur_profile
                    if reclamation.equipe_affectee.superviseur == superviseur:
                        return True

            return False

        # Création/Modification/Suppression: SEUL le créateur
        return reclamation.createur == user
