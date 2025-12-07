import django_filters
from .models import (
    Site, SousSite, Arbre, Gazon, Palmier, Arbuste, Vivace, Cactus, Graminee,
    Puit, Pompe, Vanne, Clapet, Canalisation, Aspersion, Goutte, Ballon
)

# ==============================================================================
# FILTRES POUR LA HIÉRARCHIE SPATIALE
# ==============================================================================

class SiteFilter(django_filters.FilterSet):
    class Meta:
        model = Site
        fields = {
            'nom_site': ['icontains'],
            'code_site': ['exact', 'icontains'],
            'actif': ['exact'],
            'date_debut_contrat': ['gte', 'lte'],
            'date_fin_contrat': ['gte', 'lte'],
            'superficie_totale': ['gte', 'lte'],
        }


class SousSiteFilter(django_filters.FilterSet):
    class Meta:
        model = SousSite
        fields = {
            'nom': ['icontains'],
            'site': ['exact'],
        }


# ==============================================================================
# FILTRES POUR LES VÉGÉTAUX
# ==============================================================================

class ArbreFilter(django_filters.FilterSet):
    class Meta:
        model = Arbre
        fields = {
            'nom': ['icontains'],
            'famille': ['icontains'],
            'taille': ['exact'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


class GazonFilter(django_filters.FilterSet):
    class Meta:
        model = Gazon
        fields = {
            'nom': ['icontains'],
            'famille': ['icontains'],
            'area_sqm': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


class PalmierFilter(django_filters.FilterSet):
    class Meta:
        model = Palmier
        fields = {
            'nom': ['icontains'],
            'famille': ['icontains'],
            'taille': ['exact'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


class ArbusteFilter(django_filters.FilterSet):
    class Meta:
        model = Arbuste
        fields = {
            'nom': ['icontains'],
            'famille': ['icontains'],
            'densite': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


class VivaceFilter(django_filters.FilterSet):
    class Meta:
        model = Vivace
        fields = {
            'nom': ['icontains'],
            'famille': ['icontains'],
            'densite': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


class CactusFilter(django_filters.FilterSet):
    class Meta:
        model = Cactus
        fields = {
            'nom': ['icontains'],
            'famille': ['icontains'],
            'densite': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


class GramineeFilter(django_filters.FilterSet):
    class Meta:
        model = Graminee
        fields = {
            'nom': ['icontains'],
            'famille': ['icontains'],
            'densite': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


# ==============================================================================
# FILTRES POUR L'HYDRAULIQUE
# ==============================================================================

class PuitFilter(django_filters.FilterSet):
    class Meta:
        model = Puit
        fields = {
            'nom': ['icontains'],
            'profondeur': ['gte', 'lte'],
            'diametre': ['gte', 'lte'],
            'niveau_statique': ['gte', 'lte'],
            'niveau_dynamique': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


class PompeFilter(django_filters.FilterSet):
    class Meta:
        model = Pompe
        fields = {
            'nom': ['icontains'],
            'type': ['icontains'],
            'diametre': ['gte', 'lte'],
            'puissance': ['gte', 'lte'],
            'debit': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
            'last_intervention_date': ['gte', 'lte', 'exact'],
        }


class VanneFilter(django_filters.FilterSet):
    class Meta:
        model = Vanne
        fields = {
            'marque': ['icontains'],
            'type': ['icontains'],
            'diametre': ['gte', 'lte'],
            'materiau': ['icontains'],
            'pression': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
        }


class ClapetFilter(django_filters.FilterSet):
    class Meta:
        model = Clapet
        fields = {
            'marque': ['icontains'],
            'type': ['icontains'],
            'diametre': ['gte', 'lte'],
            'materiau': ['icontains'],
            'pression': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
        }


class CanalisationFilter(django_filters.FilterSet):
    class Meta:
        model = Canalisation
        fields = {
            'marque': ['icontains'],
            'type': ['icontains'],
            'diametre': ['gte', 'lte'],
            'materiau': ['icontains'],
            'pression': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
        }


class AspersionFilter(django_filters.FilterSet):
    class Meta:
        model = Aspersion
        fields = {
            'marque': ['icontains'],
            'type': ['icontains'],
            'diametre': ['gte', 'lte'],
            'materiau': ['icontains'],
            'pression': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
        }


class GoutteFilter(django_filters.FilterSet):
    class Meta:
        model = Goutte
        fields = {
            'type': ['icontains'],
            'diametre': ['gte', 'lte'],
            'materiau': ['icontains'],
            'pression': ['gte', 'lte'],
            'site': ['exact'],
            'sous_site': ['exact'],
        }


class BallonFilter(django_filters.FilterSet):
    class Meta:
        model = Ballon
        fields = {
            'marque': ['icontains'],
            'volume': ['gte', 'lte'],
            'pression': ['gte', 'lte'],
            'materiau': ['icontains'],
            'site': ['exact'],
            'sous_site': ['exact'],
        }
