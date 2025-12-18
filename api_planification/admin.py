from django.contrib import admin
from .models import TypeTache, Tache, RatioProductivite, ParticipationTache

@admin.register(TypeTache)
class TypeTacheAdmin(admin.ModelAdmin):
    list_display = ('nom_tache', 'symbole', 'productivite_theorique')
    search_fields = ('nom_tache', 'symbole', 'description')
    ordering = ('nom_tache',)
    verbose_name = "Type de tâche"

class ParticipationTacheInline(admin.TabularInline):
    model = ParticipationTache
    extra = 1

@admin.register(Tache)
class TacheAdmin(admin.ModelAdmin):
    list_display = (
        'id_type_tache', 
        'id_client', 
        'date_debut_planifiee', 
        'date_fin_planifiee', 
        'statut', 
        'priorite',
        'notifiee',
        'confirmee'
    )
    list_filter = (
        'statut', 
        'priorite', 
        'date_debut_planifiee', 
        'id_type_tache', 
        'id_client',
        'notifiee',
        'confirmee'
    )
    search_fields = (
        'id_type_tache__nom_tache', 
        'id_client__nom_structure', 
        'commentaires', 
        'description_travaux'
    )
    date_hierarchy = 'date_debut_planifiee'
    inlines = [ParticipationTacheInline]
    filter_horizontal = ('equipes', 'objets')
    ordering = ('-date_debut_planifiee',)

@admin.register(RatioProductivite)
class RatioProductiviteAdmin(admin.ModelAdmin):
    list_display = ('id_type_tache', 'type_objet', 'ratio', 'unite_mesure', 'actif')
    list_filter = ('id_type_tache', 'type_objet', 'unite_mesure', 'actif')
    search_fields = ('type_objet', 'description')
    ordering = ('id_type_tache', 'type_objet')

@admin.register(ParticipationTache)
class ParticipationTacheAdmin(admin.ModelAdmin):
    list_display = ('id_tache', 'id_operateur', 'role', 'heures_travaillees')
    list_filter = ('role',)
    search_fields = ('id_tache__id_type_tache__nom_tache', 'id_operateur__utilisateur__nom')
