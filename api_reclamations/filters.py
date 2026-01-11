import django_filters
from .models import Reclamation


class ReclamationFilter(django_filters.FilterSet):
    """
    FilterSet personnalisé pour les réclamations.

    Supporte:
    - Filtrage exact par statut, site, zone, urgence, type, créateur
    - Filtrage par plage de dates (date_creation)
    - Recherche textuelle (numero_reclamation, description)
    """
    # Filtres de plage de dates
    date_debut = django_filters.DateFilter(
        field_name='date_creation',
        lookup_expr='gte',
        label='Date de création (à partir de)'
    )
    date_fin = django_filters.DateFilter(
        field_name='date_creation',
        lookup_expr='lte',
        label='Date de création (jusqu\'à)'
    )

    class Meta:
        model = Reclamation
        fields = {
            'statut': ['exact'],
            'site': ['exact'],
            'zone': ['exact'],
            'urgence': ['exact'],
            'type_reclamation': ['exact'],
            'createur': ['exact'],
        }
