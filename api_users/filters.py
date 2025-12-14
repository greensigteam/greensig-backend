# api_users/filters.py
import django_filters
from django.db.models import Q

from .models import (
    Utilisateur, Operateur, Equipe, Absence,
    Competence, CompetenceOperateur, HistoriqueEquipeOperateur,
    StatutOperateur, StatutAbsence, TypeAbsence,
    CategorieCompetence, NiveauCompetence, StatutEquipe
)


# ==============================================================================
# FILTRE UTILISATEUR
# ==============================================================================

class UtilisateurFilter(django_filters.FilterSet):
    """Filtre pour les utilisateurs."""

    # Recherche textuelle
    search = django_filters.CharFilter(method='filter_search', label='Recherche')

    # Filtres simples
    actif = django_filters.BooleanFilter()

    # Filtres par date
    date_creation_min = django_filters.DateFilter(
        field_name='date_creation',
        lookup_expr='gte',
        label='Cree apres'
    )
    date_creation_max = django_filters.DateFilter(
        field_name='date_creation',
        lookup_expr='lte',
        label='Cree avant'
    )

    # Filtre par role
    role = django_filters.CharFilter(
        method='filter_by_role',
        label='Role'
    )

    class Meta:
        model = Utilisateur
        fields = ['actif']

    def filter_search(self, queryset, name, value):
        """Recherche dans nom, prenom, email."""
        if value:
            return queryset.filter(
                Q(nom__icontains=value) |
                Q(prenom__icontains=value) |
                Q(email__icontains=value)
            )
        return queryset

    def filter_by_role(self, queryset, name, value):
        """Filtre les utilisateurs par role."""
        if value:
            return queryset.filter(roles_utilisateur__role__nom_role=value)
        return queryset


# ==============================================================================
# FILTRE OPERATEUR
# ==============================================================================

class OperateurFilter(django_filters.FilterSet):
    """Filtre pour les operateurs."""

    # Recherche textuelle
    search = django_filters.CharFilter(method='filter_search', label='Recherche')

    # Filtres simples
    statut = django_filters.ChoiceFilter(choices=StatutOperateur.choices)
    actif = django_filters.BooleanFilter(
        field_name='utilisateur__actif',
        label='Actif'
    )

    # Filtre par equipe
    equipe = django_filters.NumberFilter(field_name='equipe_id')
    sans_equipe = django_filters.BooleanFilter(
        method='filter_sans_equipe',
        label='Sans equipe'
    )

    # Filtre par competence
    competence = django_filters.NumberFilter(
        method='filter_by_competence',
        label='Competence ID'
    )
    competence_nom = django_filters.CharFilter(
        method='filter_by_competence_nom',
        label='Nom competence'
    )
    niveau_minimum = django_filters.ChoiceFilter(
        choices=NiveauCompetence.choices,
        method='filter_by_niveau_minimum',
        label='Niveau minimum'
    )

    # Filtre disponibilite
    disponible = django_filters.BooleanFilter(
        method='filter_disponible',
        label='Disponible aujourd\'hui'
    )

    # Filtre chef d'equipe
    est_chef = django_filters.BooleanFilter(
        method='filter_est_chef',
        label='Est chef d\'equipe'
    )
    peut_etre_chef = django_filters.BooleanFilter(
        method='filter_peut_etre_chef',
        label='Peut etre chef'
    )

    # Filtres par date d'embauche
    date_embauche_min = django_filters.DateFilter(
        field_name='date_embauche',
        lookup_expr='gte',
        label='Embauche apres'
    )
    date_embauche_max = django_filters.DateFilter(
        field_name='date_embauche',
        lookup_expr='lte',
        label='Embauche avant'
    )

    class Meta:
        model = Operateur
        fields = ['statut', 'equipe']

    def filter_search(self, queryset, name, value):
        """Recherche dans nom, prenom, email, matricule."""
        if value:
            return queryset.filter(
                Q(utilisateur__nom__icontains=value) |
                Q(utilisateur__prenom__icontains=value) |
                Q(utilisateur__email__icontains=value) |
                Q(numero_immatriculation__icontains=value)
            )
        return queryset

    def filter_sans_equipe(self, queryset, name, value):
        """Filtre les operateurs sans equipe."""
        if value:
            return queryset.filter(equipe__isnull=True)
        return queryset.filter(equipe__isnull=False)

    def filter_by_competence(self, queryset, name, value):
        """Filtre par competence ID."""
        if value:
            return queryset.filter(
                competences_operateur__competence_id=value
            ).exclude(
                competences_operateur__niveau=NiveauCompetence.NON
            ).distinct()
        return queryset

    def filter_by_competence_nom(self, queryset, name, value):
        """Filtre par nom de competence."""
        if value:
            return queryset.filter(
                competences_operateur__competence__nom_competence__icontains=value
            ).exclude(
                competences_operateur__niveau=NiveauCompetence.NON
            ).distinct()
        return queryset

    def filter_by_niveau_minimum(self, queryset, name, value):
        """Filtre par niveau minimum de competence."""
        if value:
            niveaux = ['NON', 'DEBUTANT', 'INTERMEDIAIRE', 'EXPERT']
            try:
                idx = niveaux.index(value)
                niveaux_valides = niveaux[idx:]
                return queryset.filter(
                    competences_operateur__niveau__in=niveaux_valides
                ).distinct()
            except ValueError:
                pass
        return queryset

    def filter_disponible(self, queryset, name, value):
        """Filtre les operateurs disponibles aujourd'hui."""
        from django.utils import timezone
        today = timezone.now().date()

        if value:
            return queryset.filter(
                utilisateur__actif=True,
                statut=StatutOperateur.ACTIF
            ).exclude(
                absences__statut=StatutAbsence.VALIDEE,
                absences__date_debut__lte=today,
                absences__date_fin__gte=today
            ).distinct()
        else:
            # Retourne les non-disponibles
            return queryset.filter(
                Q(utilisateur__actif=False) |
                Q(statut__in=[StatutOperateur.INACTIF, StatutOperateur.EN_CONGE]) |
                Q(
                    absences__statut=StatutAbsence.VALIDEE,
                    absences__date_debut__lte=today,
                    absences__date_fin__gte=today
                )
            ).distinct()

    def filter_est_chef(self, queryset, name, value):
        """Filtre les chefs d'equipe."""
        if value:
            return queryset.filter(equipes_dirigees__actif=True).distinct()
        return queryset.exclude(equipes_dirigees__actif=True)

    def filter_peut_etre_chef(self, queryset, name, value):
        """Filtre les operateurs pouvant etre chef."""
        if value:
            return queryset.filter(
                competences_operateur__competence__nom_competence='Gestion d\'equipe',
                competences_operateur__niveau__in=[
                    NiveauCompetence.INTERMEDIAIRE,
                    NiveauCompetence.EXPERT
                ]
            ).distinct()
        return queryset


# ==============================================================================
# FILTRE EQUIPE
# ==============================================================================

class EquipeFilter(django_filters.FilterSet):
    """Filtre pour les equipes."""

    # Recherche textuelle
    search = django_filters.CharFilter(method='filter_search', label='Recherche')

    # Filtres simples
    actif = django_filters.BooleanFilter()
    specialite = django_filters.CharFilter(lookup_expr='icontains')

    # Filtre par chef
    chef_equipe = django_filters.NumberFilter(field_name='chef_equipe_id')

    # Filtre par statut operationnel
    statut_operationnel = django_filters.ChoiceFilter(
        choices=StatutEquipe.choices,
        method='filter_statut_operationnel',
        label='Statut operationnel'
    )

    # Filtre par nombre de membres
    membres_min = django_filters.NumberFilter(
        method='filter_membres_min',
        label='Membres minimum'
    )
    membres_max = django_filters.NumberFilter(
        method='filter_membres_max',
        label='Membres maximum'
    )

    class Meta:
        model = Equipe
        fields = ['actif', 'chef_equipe', 'specialite']

    def filter_search(self, queryset, name, value):
        """Recherche dans nom equipe et specialite."""
        if value:
            return queryset.filter(
                Q(nom_equipe__icontains=value) |
                Q(specialite__icontains=value) |
                Q(chef_equipe__utilisateur__nom__icontains=value) |
                Q(chef_equipe__utilisateur__prenom__icontains=value)
            )
        return queryset

    def filter_statut_operationnel(self, queryset, name, value):
        """Filtre par statut operationnel calcule."""
        if value:
            # On doit filtrer en Python car c'est une propriete calculee
            ids = [e.id for e in queryset if e.statut_operationnel == value]
            return queryset.filter(id__in=ids)
        return queryset

    def filter_membres_min(self, queryset, name, value):
        """Filtre les equipes avec au moins N membres."""
        if value:
            ids = [e.id for e in queryset if e.nombre_membres >= value]
            return queryset.filter(id__in=ids)
        return queryset

    def filter_membres_max(self, queryset, name, value):
        """Filtre les equipes avec au plus N membres."""
        if value:
            ids = [e.id for e in queryset if e.nombre_membres <= value]
            return queryset.filter(id__in=ids)
        return queryset


# ==============================================================================
# FILTRE ABSENCE
# ==============================================================================

class AbsenceFilter(django_filters.FilterSet):
    """Filtre pour les absences."""

    # Filtres simples
    operateur = django_filters.NumberFilter(field_name='operateur_id')
    type_absence = django_filters.ChoiceFilter(choices=TypeAbsence.choices)
    statut = django_filters.ChoiceFilter(choices=StatutAbsence.choices)

    # Filtre par equipe
    equipe = django_filters.NumberFilter(
        field_name='operateur__equipe_id',
        label='Equipe'
    )

    # Filtres par date
    date_debut_min = django_filters.DateFilter(
        field_name='date_debut',
        lookup_expr='gte',
        label='Debut apres'
    )
    date_debut_max = django_filters.DateFilter(
        field_name='date_debut',
        lookup_expr='lte',
        label='Debut avant'
    )
    date_fin_min = django_filters.DateFilter(
        field_name='date_fin',
        lookup_expr='gte',
        label='Fin apres'
    )
    date_fin_max = django_filters.DateFilter(
        field_name='date_fin',
        lookup_expr='lte',
        label='Fin avant'
    )

    # Filtre en cours
    en_cours = django_filters.BooleanFilter(
        method='filter_en_cours',
        label='En cours aujourd\'hui'
    )

    # Recherche
    search = django_filters.CharFilter(method='filter_search', label='Recherche')

    class Meta:
        model = Absence
        fields = ['operateur', 'type_absence', 'statut']

    def filter_en_cours(self, queryset, name, value):
        """Filtre les absences en cours aujourd'hui."""
        from django.utils import timezone
        today = timezone.now().date()

        if value:
            return queryset.filter(
                statut=StatutAbsence.VALIDEE,
                date_debut__lte=today,
                date_fin__gte=today
            )
        return queryset

    def filter_search(self, queryset, name, value):
        """Recherche dans operateur et motif."""
        if value:
            return queryset.filter(
                Q(operateur__utilisateur__nom__icontains=value) |
                Q(operateur__utilisateur__prenom__icontains=value) |
                Q(motif__icontains=value)
            )
        return queryset


# ==============================================================================
# FILTRE COMPETENCE
# ==============================================================================

class CompetenceFilter(django_filters.FilterSet):
    """Filtre pour les competences."""

    # Filtres simples
    categorie = django_filters.ChoiceFilter(choices=CategorieCompetence.choices)

    # Recherche
    search = django_filters.CharFilter(method='filter_search', label='Recherche')

    class Meta:
        model = Competence
        fields = ['categorie']

    def filter_search(self, queryset, name, value):
        """Recherche dans nom et description."""
        if value:
            return queryset.filter(
                Q(nom_competence__icontains=value) |
                Q(description__icontains=value)
            )
        return queryset


# ==============================================================================
# FILTRE HISTORIQUE EQUIPE
# ==============================================================================

class HistoriqueEquipeFilter(django_filters.FilterSet):
    """Filtre pour l'historique des equipes."""

    # Filtres simples
    operateur = django_filters.NumberFilter(field_name='operateur_id')
    equipe = django_filters.NumberFilter(field_name='equipe_id')

    # Filtres par date
    date_debut_min = django_filters.DateFilter(
        field_name='date_debut',
        lookup_expr='gte',
        label='Debut apres'
    )
    date_debut_max = django_filters.DateFilter(
        field_name='date_debut',
        lookup_expr='lte',
        label='Debut avant'
    )

    # Filtre actif (sans date de fin)
    actif = django_filters.BooleanFilter(
        method='filter_actif',
        label='Affectation active'
    )

    # Filtre par role
    role_dans_equipe = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = HistoriqueEquipeOperateur
        fields = ['operateur', 'equipe', 'role_dans_equipe']

    def filter_actif(self, queryset, name, value):
        """Filtre les affectations actives (sans date de fin)."""
        if value:
            return queryset.filter(date_fin__isnull=True)
        return queryset.filter(date_fin__isnull=False)
