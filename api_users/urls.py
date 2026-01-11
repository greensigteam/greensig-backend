# api_users/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    UtilisateurViewSet, RoleViewSet, ClientViewSet, SuperviseurViewSet,
    CompetenceViewSet, OperateurViewSet, EquipeViewSet,
    AbsenceViewSet, HistoriqueRHView, StatistiquesUtilisateursView,
    MeView, StructureClientViewSet
)

# Configuration du routeur DRF
router = DefaultRouter()
router.register(r'utilisateurs', UtilisateurViewSet, basename='utilisateur')
router.register(r'roles', RoleViewSet, basename='role')
router.register(r'clients', ClientViewSet, basename='client')
router.register(r'structures', StructureClientViewSet, basename='structure')
router.register(r'superviseurs', SuperviseurViewSet, basename='superviseur')
router.register(r'competences', CompetenceViewSet, basename='competence')
router.register(r'operateurs', OperateurViewSet, basename='operateur')
router.register(r'equipes', EquipeViewSet, basename='equipe')
router.register(r'absences', AbsenceViewSet, basename='absence')

app_name = 'api_users'

urlpatterns = [
    # Routes du routeur DRF
    path('', include(router.urls)),

    # Routes personnalisees
    path('historique-rh/', HistoriqueRHView.as_view(), name='historique-rh'),
    path('statistiques/', StatistiquesUtilisateursView.as_view(), name='statistiques'),
    path('me/', MeView.as_view(), name='me'),
]

# ==============================================================================
# DOCUMENTATION DES ENDPOINTS
# ==============================================================================
#
# UTILISATEURS (/api/users/utilisateurs/)
# ----------------------------------------
# GET    /utilisateurs/                    - Liste des utilisateurs
# POST   /utilisateurs/                    - Creer un utilisateur
# GET    /utilisateurs/{id}/               - Detail d'un utilisateur
# PUT    /utilisateurs/{id}/               - Mettre a jour un utilisateur
# PATCH  /utilisateurs/{id}/               - Mise a jour partielle
# DELETE /utilisateurs/{id}/               - Desactiver un utilisateur (soft delete)
# POST   /utilisateurs/{id}/change_password/ - Changer le mot de passe
# POST   /utilisateurs/{id}/activer/       - Reactiver un utilisateur
# GET    /utilisateurs/{id}/roles/         - Liste des roles d'un utilisateur
# POST   /utilisateurs/{id}/attribuer_role/ - Attribuer un role
#
# ROLES (/api/users/roles/)
# -------------------------
# GET    /roles/                           - Liste des roles
# POST   /roles/                           - Creer un role
# GET    /roles/{id}/                      - Detail d'un role
# PUT    /roles/{id}/                      - Mettre a jour un role
# DELETE /roles/{id}/                      - Supprimer un role
#
# STRUCTURES CLIENTS (/api/users/structures/)
# -------------------------------------------
# GET    /structures/                      - Liste des structures clientes
# POST   /structures/                      - Creer une structure
# GET    /structures/{id}/                 - Detail d'une structure
# PUT    /structures/{id}/                 - Mettre a jour une structure
# DELETE /structures/{id}/                 - Desactiver une structure
# GET    /structures/{id}/utilisateurs/    - Liste des utilisateurs de la structure
# POST   /structures/{id}/ajouter_utilisateur/ - Ajouter un utilisateur a la structure
#
# CLIENTS (/api/users/clients/)
# -----------------------------
# GET    /clients/                         - Liste des clients (utilisateurs)
# POST   /clients/                         - Creer un client (avec utilisateur et structure)
# GET    /clients/{id}/                    - Detail d'un client
# PUT    /clients/{id}/                    - Mettre a jour un client
# DELETE /clients/{id}/                    - Desactiver un client
# GET    /clients/{id}/inventory-stats/    - Statistiques d'inventaire du client
#
# SUPERVISEURS (/api/users/superviseurs/)
# ---------------------------------------
# GET    /superviseurs/                    - Liste des superviseurs
# POST   /superviseurs/                    - Creer un superviseur (ADMIN uniquement)
# GET    /superviseurs/{id}/               - Detail d'un superviseur
# PUT    /superviseurs/{id}/               - Mettre a jour un superviseur (ADMIN ou lui-meme)
# DELETE /superviseurs/{id}/               - Desactiver un superviseur (ADMIN uniquement)
# GET    /superviseurs/{id}/equipes/       - Equipes gerees par le superviseur
# GET    /superviseurs/{id}/operateurs/    - Operateurs supervises
# GET    /superviseurs/{id}/statistiques/  - Statistiques du superviseur
# GET    /superviseurs/me/                 - Profil du superviseur connecte
#
# COMPETENCES (/api/users/competences/)
# -------------------------------------
# GET    /competences/                     - Liste des competences
# POST   /competences/                     - Creer une competence
# GET    /competences/{id}/                - Detail d'une competence
# PUT    /competences/{id}/                - Mettre a jour une competence
# DELETE /competences/{id}/                - Supprimer une competence
# GET    /competences/{id}/operateurs/     - Operateurs ayant cette competence
#
# OPERATEURS (/api/users/operateurs/)
# -----------------------------------
# GET    /operateurs/                      - Liste des operateurs
# POST   /operateurs/                      - Creer un operateur (avec utilisateur)
# GET    /operateurs/{id}/                 - Detail d'un operateur
# PUT    /operateurs/{id}/                 - Mettre a jour un operateur
# DELETE /operateurs/{id}/                 - Desactiver un operateur
# GET    /operateurs/{id}/competences/     - Competences d'un operateur
# POST   /operateurs/{id}/affecter_competence/ - Affecter une competence
# PUT    /operateurs/{id}/modifier_niveau_competence/ - Modifier niveau
# GET    /operateurs/{id}/absences/        - Absences d'un operateur
# GET    /operateurs/{id}/historique_equipes/ - Historique equipes
# GET    /operateurs/disponibles/          - Operateurs disponibles aujourd'hui
# GET    /operateurs/chefs_potentiels/     - Operateurs pouvant etre chef
# GET    /operateurs/par_competence/       - Filtrer par competence
#
# EQUIPES (/api/users/equipes/)
# -----------------------------
# GET    /equipes/                         - Liste des equipes
# POST   /equipes/                         - Creer une equipe
# GET    /equipes/{id}/                    - Detail d'une equipe
# PUT    /equipes/{id}/                    - Mettre a jour une equipe
# DELETE /equipes/{id}/                    - Desactiver une equipe
# GET    /equipes/{id}/membres/            - Membres d'une equipe
# POST   /equipes/{id}/affecter_membres/   - Affecter des membres
# POST   /equipes/{id}/retirer_membre/     - Retirer un membre
# GET    /equipes/{id}/statut/             - Statut operationnel detaille
# GET    /equipes/{id}/historique/         - Historique des membres
#
# ABSENCES (/api/users/absences/)
# -------------------------------
# GET    /absences/                        - Liste des absences
# POST   /absences/                        - Creer une absence
# GET    /absences/{id}/                   - Detail d'une absence
# PUT    /absences/{id}/                   - Mettre a jour une absence
# DELETE /absences/{id}/                   - Supprimer une absence
# POST   /absences/{id}/valider/           - Valider une absence
# POST   /absences/{id}/refuser/           - Refuser une absence
# POST   /absences/{id}/annuler/           - Annuler une absence
# GET    /absences/en_cours/               - Absences en cours aujourd'hui
# GET    /absences/a_valider/              - Absences en attente de validation
# GET    /absences/equipes_impactees/      - Equipes impactees par des absences
#
# HISTORIQUE RH (/api/users/historique-rh/)
# -----------------------------------------
# GET    /historique-rh/                   - Historique RH complet
#        Params: operateur_id, equipe_id, date_debut, date_fin, type
#
# STATISTIQUES (/api/users/statistiques/)
# ---------------------------------------
# GET    /statistiques/                    - Statistiques du module utilisateurs
#
