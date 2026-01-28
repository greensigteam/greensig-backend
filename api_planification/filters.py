"""
Filtres Django pour l'API de planification.

Utilise django-filter pour permettre des requêtes filtrées avancées
sur les distributions de charges et les tâches.
"""

import django_filters
from django.db.models import Q
from .models import DistributionCharge, Tache


class DistributionChargeFilter(django_filters.FilterSet):
    """
    FilterSet complet pour les distributions de charges.

    Permet de filtrer par :
    - Statut (status)
    - Date (exacte, période, relative)
    - Tâche et ses relations (équipe, site, structure)
    - Motif de report/annulation
    - Recherche textuelle

    Exemples d'utilisation :
        /distributions/?status=NON_REALISEE
        /distributions/?status__in=NON_REALISEE,EN_COURS
        /distributions/?date=2026-01-22
        /distributions/?date__gte=2026-01-01&date__lte=2026-01-31
        /distributions/?tache=123
        /distributions/?equipe=5
        /distributions/?site=10
        /distributions/?structure=3
        /distributions/?priorite__gte=4
        /distributions/?est_report=true
        /distributions/?search=élagage
    """

    # ==========================================================================
    # FILTRES PAR STATUT
    # ==========================================================================

    status = django_filters.ChoiceFilter(
        choices=DistributionCharge.STATUT_CHOICES,
        help_text="Statut exact (NON_REALISEE, EN_COURS, REALISEE, REPORTEE, ANNULEE)"
    )

    status__in = django_filters.BaseInFilter(
        field_name='status',
        help_text="Liste de statuts separes par virgule (ex: NON_REALISEE,EN_COURS)"
    )

    # Raccourcis pratiques pour les statuts courants
    actif = django_filters.BooleanFilter(
        method='filter_actif',
        help_text="true = NON_REALISEE, EN_COURS (travail a faire)"
    )

    termine = django_filters.BooleanFilter(
        method='filter_termine',
        help_text="true = REALISEE, REPORTEE, ANNULEE (pas de travail a faire)"
    )

    # ==========================================================================
    # FILTRES PAR DATE
    # ==========================================================================

    date = django_filters.DateFilter(
        help_text="Date exacte (YYYY-MM-DD)"
    )

    date__gte = django_filters.DateFilter(
        field_name='date',
        lookup_expr='gte',
        help_text="Date >= (YYYY-MM-DD)"
    )

    date__lte = django_filters.DateFilter(
        field_name='date',
        lookup_expr='lte',
        help_text="Date <= (YYYY-MM-DD)"
    )

    date__gt = django_filters.DateFilter(
        field_name='date',
        lookup_expr='gt',
        help_text="Date > (YYYY-MM-DD)"
    )

    date__lt = django_filters.DateFilter(
        field_name='date',
        lookup_expr='lt',
        help_text="Date < (YYYY-MM-DD)"
    )

    # Alias pour compatibilité avec l'existant
    date_debut = django_filters.DateFilter(
        field_name='date',
        lookup_expr='gte',
        help_text="Alias pour date__gte"
    )

    date_fin = django_filters.DateFilter(
        field_name='date',
        lookup_expr='lte',
        help_text="Alias pour date__lte"
    )

    # Filtres relatifs (aujourd'hui, semaine, mois)
    aujourd_hui = django_filters.BooleanFilter(
        method='filter_aujourd_hui',
        help_text="true = distributions du jour"
    )

    semaine_courante = django_filters.BooleanFilter(
        method='filter_semaine_courante',
        help_text="true = distributions de la semaine courante (lun-dim)"
    )

    # ==========================================================================
    # FILTRES PAR TÂCHE
    # ==========================================================================

    tache = django_filters.NumberFilter(
        field_name='tache_id',
        help_text="ID de la tâche"
    )

    tache__reference = django_filters.CharFilter(
        field_name='tache__reference',
        lookup_expr='icontains',
        help_text="Référence de la tâche (recherche partielle)"
    )

    # ==========================================================================
    # FILTRES PAR ÉQUIPE (via la tâche)
    # ==========================================================================

    equipe = django_filters.NumberFilter(
        method='filter_equipe',
        help_text="ID de l'équipe assignée à la tâche"
    )

    # ==========================================================================
    # FILTRES PAR SITE (via les objets de la tâche)
    # ==========================================================================

    site = django_filters.NumberFilter(
        method='filter_site',
        help_text="ID du site (via les objets de la tâche)"
    )

    site__nom = django_filters.CharFilter(
        method='filter_site_nom',
        help_text="Nom du site (recherche partielle)"
    )

    # ==========================================================================
    # FILTRES PAR STRUCTURE CLIENT
    # ==========================================================================

    structure = django_filters.NumberFilter(
        field_name='tache__id_structure_client_id',
        help_text="ID de la structure client"
    )

    # ==========================================================================
    # FILTRES PAR PRIORITÉ DE LA TÂCHE
    # ==========================================================================

    priorite = django_filters.NumberFilter(
        field_name='tache__priorite',
        help_text="Priorité exacte de la tâche (1-5)"
    )

    priorite__gte = django_filters.NumberFilter(
        field_name='tache__priorite',
        lookup_expr='gte',
        help_text="Priorité >= (1-5)"
    )

    priorite__lte = django_filters.NumberFilter(
        field_name='tache__priorite',
        lookup_expr='lte',
        help_text="Priorité <= (1-5)"
    )

    urgent = django_filters.BooleanFilter(
        method='filter_urgent',
        help_text="true = priorité >= 4 (haute ou urgente)"
    )

    # ==========================================================================
    # FILTRES PAR TYPE DE TÂCHE
    # ==========================================================================

    type_tache = django_filters.NumberFilter(
        field_name='tache__id_type_tache_id',
        help_text="ID du type de tâche"
    )

    type_tache__nom = django_filters.CharFilter(
        field_name='tache__id_type_tache__nom_tache',
        lookup_expr='icontains',
        help_text="Nom du type de tâche (recherche partielle)"
    )

    # ==========================================================================
    # FILTRES PAR MOTIF
    # ==========================================================================

    motif = django_filters.ChoiceFilter(
        field_name='motif_report_annulation',
        choices=DistributionCharge.MOTIF_CHOICES,
        help_text="Motif de report/annulation"
    )

    # ==========================================================================
    # FILTRES POUR LES REPORTS
    # ==========================================================================

    est_report = django_filters.BooleanFilter(
        method='filter_est_report',
        help_text="true = distributions issues d'un report"
    )

    a_remplacement = django_filters.BooleanFilter(
        method='filter_a_remplacement',
        help_text="true = distributions qui ont été reportées"
    )

    # ==========================================================================
    # RECHERCHE TEXTUELLE
    # ==========================================================================

    search = django_filters.CharFilter(
        method='filter_search',
        help_text="Recherche dans référence, commentaire, type de tâche"
    )

    # ==========================================================================
    # FILTRES PAR HEURES
    # ==========================================================================

    heures_planifiees__gte = django_filters.NumberFilter(
        field_name='heures_planifiees',
        lookup_expr='gte',
        help_text="Heures planifiées >="
    )

    heures_planifiees__lte = django_filters.NumberFilter(
        field_name='heures_planifiees',
        lookup_expr='lte',
        help_text="Heures planifiées <="
    )

    # ==========================================================================
    # TRI
    # ==========================================================================

    ordering = django_filters.OrderingFilter(
        fields=(
            ('date', 'date'),
            ('status', 'status'),
            ('heures_planifiees', 'heures_planifiees'),
            ('tache__priorite', 'priorite'),
            ('created_at', 'created_at'),
        ),
        help_text="Tri: date, -date, status, priorite, etc."
    )

    class Meta:
        model = DistributionCharge
        fields = []  # Tous les filtres sont définis explicitement ci-dessus

    # ==========================================================================
    # MÉTHODES DE FILTRAGE CUSTOM
    # ==========================================================================

    def filter_actif(self, queryset, name, value):
        """Filtre les distributions actives (travail a faire)."""
        if value:
            return queryset.filter(status__in=['NON_REALISEE', 'EN_COURS'])
        return queryset.exclude(status__in=['NON_REALISEE', 'EN_COURS'])

    def filter_termine(self, queryset, name, value):
        """Filtre les distributions terminées."""
        if value:
            return queryset.filter(status__in=['REALISEE', 'REPORTEE', 'ANNULEE'])
        return queryset.exclude(status__in=['REALISEE', 'REPORTEE', 'ANNULEE'])

    def filter_aujourd_hui(self, queryset, name, value):
        """Filtre les distributions du jour."""
        from django.utils import timezone
        today = timezone.now().date()
        if value:
            return queryset.filter(date=today)
        return queryset.exclude(date=today)

    def filter_semaine_courante(self, queryset, name, value):
        """Filtre les distributions de la semaine courante (lundi à dimanche)."""
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.now().date()
        # Lundi de la semaine courante
        start_of_week = today - timedelta(days=today.weekday())
        # Dimanche de la semaine courante
        end_of_week = start_of_week + timedelta(days=6)

        if value:
            return queryset.filter(date__gte=start_of_week, date__lte=end_of_week)
        return queryset.exclude(date__gte=start_of_week, date__lte=end_of_week)

    def filter_equipe(self, queryset, name, value):
        """Filtre par équipe assignée à la tâche."""
        return queryset.filter(
            Q(tache__equipes__id=value) | Q(tache__id_equipe_id=value)
        ).distinct()

    def filter_site(self, queryset, name, value):
        """Filtre par site (via les objets de la tâche)."""
        return queryset.filter(tache__objets__site_id=value).distinct()

    def filter_site_nom(self, queryset, name, value):
        """Filtre par nom de site (recherche partielle)."""
        return queryset.filter(tache__objets__site__nom_site__icontains=value).distinct()

    def filter_urgent(self, queryset, name, value):
        """Filtre les distributions de tâches urgentes (priorité >= 4)."""
        if value:
            return queryset.filter(tache__priorite__gte=4)
        return queryset.filter(tache__priorite__lt=4)

    def filter_est_report(self, queryset, name, value):
        """Filtre les distributions issues d'un report."""
        if value:
            return queryset.filter(distribution_origine__isnull=False)
        return queryset.filter(distribution_origine__isnull=True)

    def filter_a_remplacement(self, queryset, name, value):
        """Filtre les distributions qui ont été reportées."""
        if value:
            return queryset.filter(distribution_remplacement__isnull=False)
        return queryset.filter(distribution_remplacement__isnull=True)

    def filter_search(self, queryset, name, value):
        """Recherche textuelle multi-champs."""
        return queryset.filter(
            Q(reference__icontains=value) |
            Q(commentaire__icontains=value) |
            Q(tache__reference__icontains=value) |
            Q(tache__id_type_tache__nom_tache__icontains=value)
        ).distinct()
