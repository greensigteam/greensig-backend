from django.contrib import admin
from .models import Site, SousSite

@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('nom_site', 'client', 'code_site', 'actif')
    list_filter = ('client', 'actif')
    search_fields = ('nom_site', 'code_site', 'adresse')
    readonly_fields = ('code_site', 'centroid')

@admin.register(SousSite)
class SousSiteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'site')
    list_filter = ('site',)
    search_fields = ('nom', 'site__nom_site')
