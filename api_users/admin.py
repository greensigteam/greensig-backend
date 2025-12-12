# api_users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html

from .models import (
    Utilisateur, Role, UtilisateurRole, Client, Operateur,
    Competence, CompetenceOperateur, Equipe, Absence,
    HistoriqueEquipeOperateur
)


# ==============================================================================
# INLINES
# ==============================================================================

class UtilisateurRoleInline(admin.TabularInline):
    """Inline pour les roles d'un utilisateur."""
    model = UtilisateurRole
    extra = 1
    autocomplete_fields = ['role']


class CompetenceOperateurInline(admin.TabularInline):
    """Inline pour les competences d'un operateur."""
    model = CompetenceOperateur
    extra = 1
    autocomplete_fields = ['competence']


class AbsenceInline(admin.TabularInline):
    """Inline pour les absences d'un operateur."""
    model = Absence
    extra = 0
    readonly_fields = ['date_demande', 'validee_par', 'date_validation']
    fields = ['type_absence', 'date_debut', 'date_fin', 'statut', 'motif']


class OperateurInline(admin.TabularInline):
    """Inline pour les operateurs d'une equipe."""
    model = Operateur
    extra = 0
    fields = ['utilisateur', 'numero_immatriculation', 'statut']
    readonly_fields = ['utilisateur', 'numero_immatriculation']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class HistoriqueEquipeInline(admin.TabularInline):
    """Inline pour l'historique des equipes."""
    model = HistoriqueEquipeOperateur
    extra = 0
    readonly_fields = ['operateur', 'equipe', 'date_debut', 'date_fin', 'role_dans_equipe']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ==============================================================================
# ADMIN UTILISATEUR
# ==============================================================================

@admin.register(Utilisateur)
class UtilisateurAdmin(BaseUserAdmin):
    """Admin personnalise pour le modele Utilisateur."""

    list_display = [
        'email', 'nom', 'prenom', 'type_utilisateur',
        'actif', 'is_staff', 'date_creation'
    ]
    list_filter = ['type_utilisateur', 'actif', 'is_staff', 'date_creation']
    search_fields = ['email', 'nom', 'prenom']
    ordering = ['nom', 'prenom']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Informations personnelles', {'fields': ('nom', 'prenom')}),
        ('Type et statut', {'fields': ('type_utilisateur', 'actif')}),
        ('Permissions Django', {
            'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date_creation', 'derniere_connexion', 'last_login'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['date_creation', 'derniere_connexion', 'last_login']

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nom', 'prenom', 'password1', 'password2', 'type_utilisateur'),
        }),
    )

    inlines = [UtilisateurRoleInline]


# ==============================================================================
# ADMIN ROLE
# ==============================================================================

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin pour les roles."""
    list_display = ['nom_role', 'description']
    search_fields = ['nom_role', 'description']


# ==============================================================================
# ADMIN CLIENT
# ==============================================================================

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Admin pour les clients."""

    list_display = [
        'nom_structure', 'get_email', 'get_nom_complet',
        'telephone', 'contact_principal', 'get_actif'
    ]
    list_filter = ['utilisateur__actif']
    search_fields = [
        'nom_structure', 'utilisateur__email',
        'utilisateur__nom', 'utilisateur__prenom'
    ]
    autocomplete_fields = ['utilisateur']

    fieldsets = (
        ('Utilisateur', {'fields': ('utilisateur',)}),
        ('Information structure', {
            'fields': ('nom_structure', 'adresse', 'telephone')
        }),
        ('Contact et facturation', {
            'fields': ('contact_principal', 'email_facturation', 'logo')
        }),
    )

    def get_email(self, obj):
        return obj.utilisateur.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'utilisateur__email'

    def get_nom_complet(self, obj):
        return obj.utilisateur.get_full_name()
    get_nom_complet.short_description = 'Responsable'

    def get_actif(self, obj):
        return obj.utilisateur.actif
    get_actif.short_description = 'Actif'
    get_actif.boolean = True


# ==============================================================================
# ADMIN COMPETENCE
# ==============================================================================

@admin.register(Competence)
class CompetenceAdmin(admin.ModelAdmin):
    """Admin pour les competences."""

    list_display = ['nom_competence', 'categorie', 'ordre_affichage']
    list_filter = ['categorie']
    search_fields = ['nom_competence', 'description']
    ordering = ['categorie', 'ordre_affichage', 'nom_competence']


# ==============================================================================
# ADMIN OPERATEUR
# ==============================================================================

@admin.register(Operateur)
class OperateurAdmin(admin.ModelAdmin):
    """Admin pour les operateurs."""

    list_display = [
        'numero_immatriculation', 'get_nom_complet', 'get_email',
        'statut', 'equipe', 'date_embauche', 'get_actif',
        'get_est_chef', 'get_disponible'
    ]
    list_filter = ['statut', 'equipe', 'utilisateur__actif', 'date_embauche']
    search_fields = [
        'numero_immatriculation', 'utilisateur__email',
        'utilisateur__nom', 'utilisateur__prenom'
    ]
    autocomplete_fields = ['utilisateur', 'equipe']
    date_hierarchy = 'date_embauche'

    fieldsets = (
        ('Utilisateur', {'fields': ('utilisateur',)}),
        ('Information operateur', {
            'fields': ('numero_immatriculation', 'statut', 'date_embauche')
        }),
        ('Equipe', {'fields': ('equipe',)}),
        ('Contact', {'fields': ('telephone', 'photo')}),
    )

    inlines = [CompetenceOperateurInline, AbsenceInline]

    def get_nom_complet(self, obj):
        return obj.utilisateur.get_full_name()
    get_nom_complet.short_description = 'Nom complet'
    get_nom_complet.admin_order_field = 'utilisateur__nom'

    def get_email(self, obj):
        return obj.utilisateur.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'utilisateur__email'

    def get_actif(self, obj):
        return obj.utilisateur.actif
    get_actif.short_description = 'Actif'
    get_actif.boolean = True

    def get_est_chef(self, obj):
        return obj.est_chef_equipe
    get_est_chef.short_description = 'Chef'
    get_est_chef.boolean = True

    def get_disponible(self, obj):
        return obj.est_disponible
    get_disponible.short_description = 'Disponible'
    get_disponible.boolean = True


# ==============================================================================
# ADMIN EQUIPE
# ==============================================================================

@admin.register(Equipe)
class EquipeAdmin(admin.ModelAdmin):
    """Admin pour les equipes."""

    list_display = [
        'nom_equipe', 'chef_equipe', 'specialite',
        'get_nombre_membres', 'get_statut_operationnel', 'actif', 'date_creation'
    ]
    list_filter = ['actif', 'specialite', 'date_creation']
    search_fields = [
        'nom_equipe', 'specialite',
        'chef_equipe__utilisateur__nom', 'chef_equipe__utilisateur__prenom'
    ]
    autocomplete_fields = ['chef_equipe']
    date_hierarchy = 'date_creation'

    fieldsets = (
        ('Information equipe', {
            'fields': ('nom_equipe', 'specialite', 'actif')
        }),
        ('Chef d\'equipe', {'fields': ('chef_equipe',)}),
    )

    inlines = [OperateurInline]

    def get_nombre_membres(self, obj):
        return obj.nombre_membres
    get_nombre_membres.short_description = 'Membres'

    def get_statut_operationnel(self, obj):
        statut = obj.statut_operationnel
        colors = {
            'COMPLETE': 'green',
            'PARTIELLE': 'orange',
            'INDISPONIBLE': 'red'
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(statut, 'black'),
            statut
        )
    get_statut_operationnel.short_description = 'Statut operationnel'


# ==============================================================================
# ADMIN ABSENCE
# ==============================================================================

@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    """Admin pour les absences."""

    list_display = [
        'operateur', 'type_absence', 'date_debut', 'date_fin',
        'get_duree', 'statut', 'validee_par', 'date_validation'
    ]
    list_filter = ['type_absence', 'statut', 'date_debut']
    search_fields = [
        'operateur__utilisateur__nom', 'operateur__utilisateur__prenom',
        'motif'
    ]
    autocomplete_fields = ['operateur', 'validee_par']
    date_hierarchy = 'date_debut'

    fieldsets = (
        ('Operateur', {'fields': ('operateur',)}),
        ('Details absence', {
            'fields': ('type_absence', 'date_debut', 'date_fin', 'motif')
        }),
        ('Validation', {
            'fields': ('statut', 'validee_par', 'date_validation', 'commentaire')
        }),
    )

    readonly_fields = ['date_demande', 'date_validation']

    def get_duree(self, obj):
        return f"{obj.duree_jours} jour(s)"
    get_duree.short_description = 'Duree'


# ==============================================================================
# ADMIN HISTORIQUE
# ==============================================================================

@admin.register(HistoriqueEquipeOperateur)
class HistoriqueEquipeOperateurAdmin(admin.ModelAdmin):
    """Admin pour l'historique des equipes."""

    list_display = [
        'operateur', 'equipe', 'date_debut', 'date_fin',
        'role_dans_equipe', 'get_est_actif'
    ]
    list_filter = ['equipe', 'role_dans_equipe', 'date_debut']
    search_fields = [
        'operateur__utilisateur__nom', 'operateur__utilisateur__prenom',
        'equipe__nom_equipe'
    ]
    autocomplete_fields = ['operateur', 'equipe']
    date_hierarchy = 'date_debut'

    def get_est_actif(self, obj):
        return obj.date_fin is None
    get_est_actif.short_description = 'Actif'
    get_est_actif.boolean = True


# ==============================================================================
# ADMIN COMPETENCE OPERATEUR
# ==============================================================================

@admin.register(CompetenceOperateur)
class CompetenceOperateurAdmin(admin.ModelAdmin):
    """Admin pour les competences des operateurs."""

    list_display = [
        'operateur', 'competence', 'niveau',
        'date_acquisition', 'date_modification'
    ]
    list_filter = ['competence', 'niveau', 'date_acquisition']
    search_fields = [
        'operateur__utilisateur__nom', 'operateur__utilisateur__prenom',
        'competence__nom_competence'
    ]
    autocomplete_fields = ['operateur', 'competence']


# ==============================================================================
# ADMIN UTILISATEUR ROLE
# ==============================================================================

@admin.register(UtilisateurRole)
class UtilisateurRoleAdmin(admin.ModelAdmin):
    """Admin pour les attributions de roles."""

    list_display = ['utilisateur', 'role', 'date_attribution']
    list_filter = ['role', 'date_attribution']
    search_fields = ['utilisateur__email', 'utilisateur__nom']
    autocomplete_fields = ['utilisateur', 'role']
