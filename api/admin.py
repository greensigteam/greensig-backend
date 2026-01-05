"""
Admin configuration for GreenSIG core models.
Includes GIS widgets for geometry fields using OpenStreetMap tiles.
"""
from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from .models import (
    Site, SousSite,
    # Végétation
    Arbre, Palmier, Gazon, Arbuste, Vivace, Cactus, Graminee,
    # Hydraulique
    Puit, Pompe, Vanne, Clapet, Ballon, Canalisation, Aspersion, Goutte
)


# =============================================================================
# SITE & SOUS-SITE ADMIN
# =============================================================================

@admin.register(Site)
class SiteAdmin(GISModelAdmin):
    """Admin pour les Sites avec widget carte pour la géométrie."""
    list_display = ('nom_site', 'structure_client', 'superviseur', 'code_site', 'actif', 'superficie_display')
    list_filter = ('structure_client', 'superviseur', 'actif')
    search_fields = ('nom_site', 'code_site', 'adresse', 'structure_client__nom')
    readonly_fields = ('code_site', 'centroid')
    ordering = ('nom_site',)
    autocomplete_fields = ['structure_client', 'superviseur']

    fieldsets = (
        ('Informations générales', {
            'fields': ('nom_site', 'code_site', 'structure_client', 'superviseur', 'actif')
        }),
        ('Contrat', {
            'fields': ('date_debut_contrat', 'date_fin_contrat'),
            'classes': ('collapse',)
        }),
        ('Localisation', {
            'fields': ('adresse', 'superficie_totale', 'geometrie_emprise', 'centroid'),
            'description': 'Dessinez le contour du site sur la carte ci-dessous.'
        }),
        ('Champs Legacy (à supprimer)', {
            'fields': ('client',),
            'classes': ('collapse',),
            'description': 'Ancien champ client, utilisez structure_client à la place.'
        }),
    )

    def superficie_display(self, obj):
        """Affiche la superficie."""
        if obj.superficie_totale:
            if obj.superficie_totale > 10000:
                return f"{obj.superficie_totale / 10000:.2f} ha"
            return f"{obj.superficie_totale:.0f} m²"
        return "-"
    superficie_display.short_description = "Superficie"


@admin.register(SousSite)
class SousSiteAdmin(GISModelAdmin):
    """Admin pour les Sous-Sites (zones/villas)."""
    list_display = ('nom', 'site')
    list_filter = ('site',)
    search_fields = ('nom', 'site__nom_site')
    autocomplete_fields = ('site',)

    fieldsets = (
        (None, {
            'fields': ('site', 'nom', 'geometrie'),
            'description': 'Placez le point sur la carte pour localiser le sous-site.'
        }),
    )


# =============================================================================
# BASE OBJET ADMIN
# =============================================================================

class ObjetAdminBase(GISModelAdmin):
    """
    Classe de base pour l'admin des objets GIS.
    Fournit une configuration commune pour tous les types d'objets.
    """
    list_filter = ('site', 'etat')
    search_fields = ('nom', 'site__nom_site', 'sous_site__nom')
    autocomplete_fields = ('site', 'sous_site')
    ordering = ('-id',)


# =============================================================================
# VÉGÉTATION ADMIN
# =============================================================================

@admin.register(Arbre)
class ArbreAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'famille', 'site', 'taille', 'etat')
    list_filter = ('site', 'etat', 'famille', 'taille')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Placez le point sur la carte.'
        }),
        ('Informations', {
            'fields': ('nom', 'famille', 'taille', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Palmier)
class PalmierAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'famille', 'site', 'taille', 'etat')
    list_filter = ('site', 'etat', 'famille', 'taille')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Placez le point sur la carte.'
        }),
        ('Informations', {
            'fields': ('nom', 'famille', 'taille', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Gazon)
class GazonAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'famille', 'site', 'area_sqm', 'etat')
    list_filter = ('site', 'etat', 'famille')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Dessinez le polygone sur la carte.'
        }),
        ('Informations', {
            'fields': ('nom', 'famille', 'area_sqm', 'etat')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Arbuste)
class ArbusteAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'famille', 'site', 'densite', 'etat')
    list_filter = ('site', 'etat', 'famille')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Dessinez le polygone sur la carte.'
        }),
        ('Informations', {
            'fields': ('nom', 'famille', 'densite', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Vivace)
class VivaceAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'famille', 'site', 'densite', 'etat')
    list_filter = ('site', 'etat', 'famille')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Dessinez le polygone sur la carte.'
        }),
        ('Informations', {
            'fields': ('nom', 'famille', 'densite', 'etat')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Cactus)
class CactusAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'famille', 'site', 'densite', 'etat')
    list_filter = ('site', 'etat', 'famille')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Dessinez le polygone sur la carte.'
        }),
        ('Informations', {
            'fields': ('nom', 'famille', 'densite', 'etat')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Graminee)
class GramineeAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'famille', 'site', 'densite', 'etat')
    list_filter = ('site', 'etat', 'famille')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Dessinez le polygone sur la carte.'
        }),
        ('Informations', {
            'fields': ('nom', 'famille', 'densite', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# HYDRAULIQUE ADMIN
# =============================================================================

@admin.register(Puit)
class PuitAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'site', 'profondeur', 'diametre', 'etat')
    list_filter = ('site', 'etat')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Placez le point sur la carte.'
        }),
        ('Caractéristiques', {
            'fields': ('nom', 'profondeur', 'diametre', 'niveau_statique', 'niveau_dynamique', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Pompe)
class PompeAdmin(ObjetAdminBase):
    list_display = ('id', 'nom', 'type', 'site', 'puissance', 'debit', 'etat')
    list_filter = ('site', 'etat', 'type')
    search_fields = ('nom', 'type', 'site__nom_site')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Placez le point sur la carte.'
        }),
        ('Caractéristiques', {
            'fields': ('nom', 'type', 'diametre', 'puissance', 'debit', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation', 'last_intervention_date'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Vanne)
class VanneAdmin(ObjetAdminBase):
    list_display = ('id', 'marque', 'type', 'site', 'diametre', 'etat')
    list_filter = ('site', 'etat', 'type')
    search_fields = ('marque', 'type', 'site__nom_site')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Placez le point sur la carte.'
        }),
        ('Caractéristiques', {
            'fields': ('marque', 'type', 'diametre', 'materiau', 'pression', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Clapet)
class ClapetAdmin(ObjetAdminBase):
    list_display = ('id', 'marque', 'type', 'site', 'diametre', 'etat')
    list_filter = ('site', 'etat', 'type')
    search_fields = ('marque', 'type', 'site__nom_site')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Placez le point sur la carte.'
        }),
        ('Caractéristiques', {
            'fields': ('marque', 'type', 'diametre', 'materiau', 'pression', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Ballon)
class BallonAdmin(ObjetAdminBase):
    list_display = ('id', 'marque', 'site', 'volume', 'pression', 'etat')
    list_filter = ('site', 'etat')
    search_fields = ('marque', 'site__nom_site')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Placez le point sur la carte.'
        }),
        ('Caractéristiques', {
            'fields': ('marque', 'volume', 'pression', 'materiau', 'etat')
        }),
        ('Observations', {
            'fields': ('observation',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Canalisation)
class CanalisationAdmin(ObjetAdminBase):
    list_display = ('id', 'marque', 'type', 'site', 'diametre', 'materiau', 'etat')
    list_filter = ('site', 'etat', 'materiau', 'type')
    search_fields = ('marque', 'type', 'site__nom_site')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Dessinez la ligne sur la carte.'
        }),
        ('Caractéristiques', {
            'fields': ('marque', 'type', 'diametre', 'materiau', 'pression', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Aspersion)
class AspersionAdmin(ObjetAdminBase):
    list_display = ('id', 'marque', 'type', 'site', 'diametre', 'pression', 'etat')
    list_filter = ('site', 'etat', 'type')
    search_fields = ('marque', 'type', 'site__nom_site')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Dessinez la ligne sur la carte.'
        }),
        ('Caractéristiques', {
            'fields': ('marque', 'type', 'diametre', 'materiau', 'pression', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Goutte)
class GoutteAdmin(ObjetAdminBase):
    list_display = ('id', 'type', 'site', 'diametre', 'pression', 'etat')
    list_filter = ('site', 'etat', 'type')
    search_fields = ('type', 'site__nom_site')

    fieldsets = (
        ('Localisation', {
            'fields': ('site', 'sous_site')
        }),
        ('Géométrie', {
            'fields': ('geometry',),
            'description': 'Dessinez la ligne sur la carte.'
        }),
        ('Caractéristiques', {
            'fields': ('type', 'diametre', 'materiau', 'pression', 'etat', 'symbole')
        }),
        ('Observations', {
            'fields': ('observation',),
            'classes': ('collapse',)
        }),
    )


# =============================================================================
# ADMIN SITE CUSTOMIZATION
# =============================================================================

admin.site.site_header = "GreenSIG Administration"
admin.site.site_title = "GreenSIG Admin"
admin.site.index_title = "Gestion des espaces verts"
