"""
Configuration de l'interface d'administration Django pour le module Suivi des Tâches
"""
from django.contrib import admin
from .models import (
    Produit,
    ProduitMatiereActive,
    DoseProduit,
    ConsommationProduit,
    Photo
)


# ==============================================================================
# INLINE ADMINS
# ==============================================================================

class ProduitMatiereActiveInline(admin.TabularInline):
    """Inline pour les matières actives d'un produit."""
    model = ProduitMatiereActive
    extra = 1
    fields = ['matiere_active', 'teneur_valeur', 'teneur_unite', 'ordre']


class DoseProduitInline(admin.TabularInline):
    """Inline pour les doses d'un produit."""
    model = DoseProduit
    extra = 1
    fields = ['dose_valeur', 'dose_unite_produit', 'dose_unite_support', 'contexte']


# ==============================================================================
# MODEL ADMINS
# ==============================================================================

@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    """Administration des produits."""
    list_display = [
        'nom_produit',
        'numero_homologation',
        'date_validite',
        'cible',
        'actif',
        'est_valide_display'
    ]
    list_filter = ['actif', 'date_validite', 'date_creation']
    search_fields = ['nom_produit', 'numero_homologation', 'cible']
    readonly_fields = ['date_creation', 'est_valide']
    inlines = [ProduitMatiereActiveInline, DoseProduitInline]
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom_produit', 'numero_homologation', 'cible', 'description')
        }),
        ('Validité', {
            'fields': ('date_validite', 'actif', 'est_valide')
        }),
        ('Métadonnées', {
            'fields': ('date_creation',),
            'classes': ('collapse',)
        }),
    )
    
    def est_valide_display(self, obj):
        """Affiche si le produit est valide."""
        return '✓' if obj.est_valide else '✗'
    est_valide_display.short_description = 'Valide'
    est_valide_display.boolean = True


@admin.register(ProduitMatiereActive)
class ProduitMatiereActiveAdmin(admin.ModelAdmin):
    """Administration des matières actives."""
    list_display = ['produit', 'matiere_active', 'teneur_valeur', 'teneur_unite', 'ordre']
    list_filter = ['produit']
    search_fields = ['produit__nom_produit', 'matiere_active']
    ordering = ['produit', 'ordre']


@admin.register(DoseProduit)
class DoseProduitAdmin(admin.ModelAdmin):
    """Administration des doses."""
    list_display = [
        'produit',
        'dose_valeur',
        'dose_unite_produit',
        'dose_unite_support',
        'contexte'
    ]
    list_filter = ['produit']
    search_fields = ['produit__nom_produit', 'contexte']


@admin.register(ConsommationProduit)
class ConsommationProduitAdmin(admin.ModelAdmin):
    """Administration des consommations de produits."""
    list_display = [
        'tache',
        'produit',
        'quantite_utilisee',
        'unite',
        'date_utilisation'
    ]
    list_filter = ['date_utilisation', 'produit']
    search_fields = ['tache__id', 'produit__nom_produit']
    readonly_fields = ['date_utilisation']
    
    fieldsets = (
        ('Consommation', {
            'fields': ('tache', 'produit', 'quantite_utilisee', 'unite')
        }),
        ('Informations complémentaires', {
            'fields': ('commentaire', 'date_utilisation')
        }),
    )


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    """Administration des photos."""
    list_display = [
        'id',
        'type_photo',
        'tache',
        'objet',
        'date_prise',
        'has_geolocation'
    ]
    list_filter = ['type_photo', 'date_prise']
    search_fields = ['legende', 'tache__id']
    readonly_fields = ['date_prise']
    
    fieldsets = (
        ('Photo', {
            'fields': ('url_fichier', 'type_photo', 'legende')
        }),
        ('Associations', {
            'fields': ('tache', 'objet')
        }),
        ('Géolocalisation', {
            'fields': ('latitude', 'longitude'),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('date_prise',),
            'classes': ('collapse',)
        }),
    )
    
    def has_geolocation(self, obj):
        """Indique si la photo a une géolocalisation."""
        return obj.latitude is not None and obj.longitude is not None
    has_geolocation.short_description = 'Géolocalisée'
    has_geolocation.boolean = True
