from django.contrib import admin
from .models import TypeReclamation, Urgence, Reclamation

@admin.register(TypeReclamation)
class TypeReclamationAdmin(admin.ModelAdmin):
    list_display = ('nom_reclamation', 'categorie', 'actif')
    search_fields = ('nom_reclamation', 'code_reclamation')
    list_filter = ('categorie', 'actif')

@admin.register(Urgence)
class UrgenceAdmin(admin.ModelAdmin):
    list_display = ('niveau_urgence', 'couleur', 'ordre')
    ordering = ('ordre',)

@admin.register(Reclamation)
class ReclamationAdmin(admin.ModelAdmin):
    list_display = ('numero_reclamation', 'type_reclamation', 'client', 'site', 'statut', 'date_creation', 'urgence')
    list_filter = ('statut', 'urgence', 'date_creation', 'site')
    search_fields = ('numero_reclamation', 'description', 'client__nom_structure')
    readonly_fields = ('date_creation', 'numero_reclamation')
