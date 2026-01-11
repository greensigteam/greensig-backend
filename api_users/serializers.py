# api_users/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import (
    Utilisateur, Role, UtilisateurRole, StructureClient, Client, Superviseur, Operateur,
    Competence, CompetenceOperateur, Equipe, Absence, HoraireTravail, JourFerie,
    HistoriqueEquipeOperateur, StatutOperateur,
    NiveauCompetence, StatutAbsence
)

# Import Site pour les relations ManyToMany dans EquipeCreate/UpdateSerializer
from api.models import Site


# ==============================================================================
# SERIALIZERS UTILISATEUR
# ==============================================================================

class UtilisateurSerializer(serializers.ModelSerializer):
    """Serializer de base pour Utilisateur."""
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'nom', 'prenom', 'full_name',
            'date_creation', 'actif',
            'derniere_connexion', 'roles'
        ]
        read_only_fields = ['id', 'date_creation', 'derniere_connexion']

    def get_roles(self, obj):
        """Retourne la liste des rôles de l'utilisateur."""
        return [ur.role.nom_role for ur in obj.roles_utilisateur.all()]


class UtilisateurCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'utilisateur avec mot de passe."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'nom', 'prenom', 'password', 'password_confirm',
            'actif'
        ]

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                'password_confirm': "Les mots de passe ne correspondent pas."
            })
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        # Création sans rôle, l'admin attribuera les rôles ensuite
        user = Utilisateur.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class UtilisateurUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'utilisateur."""

    class Meta:
        model = Utilisateur
        fields = ['nom', 'prenom', 'email', 'actif']


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer pour le changement de mot de passe."""
    old_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': "Les nouveaux mots de passe ne correspondent pas."
            })
        return attrs


class AdminResetPasswordSerializer(serializers.Serializer):
    """Serializer pour la réinitialisation de mot de passe par un administrateur."""
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        validators=[validate_password]
    )
    new_password_confirm = serializers.CharField(required=True, write_only=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': "Les nouveaux mots de passe ne correspondent pas."
            })
        return attrs


# ==============================================================================
# SERIALIZERS ROLE
# ==============================================================================

class RoleSerializer(serializers.ModelSerializer):
    """Serializer pour les rôles."""
    nom_display = serializers.CharField(source='get_nom_role_display', read_only=True)

    class Meta:
        model = Role
        fields = ['id', 'nom_role', 'nom_display', 'description']


class UtilisateurRoleSerializer(serializers.ModelSerializer):
    """Serializer pour l'attribution de rôles."""
    role_nom = serializers.CharField(source='role.get_nom_role_display', read_only=True)
    utilisateur_email = serializers.CharField(source='utilisateur.email', read_only=True)

    class Meta:
        model = UtilisateurRole
        fields = ['id', 'utilisateur', 'utilisateur_email', 'role', 'role_nom', 'date_attribution']
        read_only_fields = ['date_attribution']


# ==============================================================================
# SERIALIZERS STRUCTURE CLIENT
# ==============================================================================

class StructureClientSerializer(serializers.ModelSerializer):
    """
    ⚡ Serializer OPTIMISÉ pour les structures clientes.

    Désactive les champs calculés coûteux pour éviter les N+1 queries.
    """
    # ⚠️ DÉSACTIVÉ: Ces champs font des .count() sur chaque structure (N+1)
    # utilisateurs_count = serializers.SerializerMethodField()  # obj.nombre_utilisateurs fait .count()
    # sites_count = serializers.SerializerMethodField()  # obj.nombre_sites fait .count()
    # logo_display = serializers.SerializerMethodField()  # Propriété calculée

    class Meta:
        model = StructureClient
        fields = [
            'id', 'nom', 'adresse', 'telephone',
            'contact_principal', 'email_facturation', 'logo', 'logo_url',
            'actif', 'date_creation'
            # Champs désactivés pour performance: utilisateurs_count, sites_count, logo_display
        ]
        read_only_fields = ['id', 'date_creation']

    # def get_utilisateurs_count(self, obj):
    #     return obj.nombre_utilisateurs
    #
    # def get_sites_count(self, obj):
    #     return obj.nombre_sites
    #
    # def get_logo_display(self, obj):
    #     """Retourne l'URL du logo (fichier ou URL externe)."""
    #     return obj.logo_display


class StructureClientDetailSerializer(StructureClientSerializer):
    """Serializer détaillé pour les structures clientes avec utilisateurs."""
    utilisateurs = serializers.SerializerMethodField()

    class Meta(StructureClientSerializer.Meta):
        fields = StructureClientSerializer.Meta.fields + ['utilisateurs']

    def get_utilisateurs(self, obj):
        """Retourne la liste des utilisateurs de la structure."""
        clients = obj.utilisateurs.select_related('utilisateur').all()
        return ClientLightSerializer(clients, many=True).data


class StructureClientCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'une structure cliente."""

    class Meta:
        model = StructureClient
        fields = [
            'nom', 'adresse', 'telephone',
            'contact_principal', 'email_facturation', 'logo', 'logo_url'
        ]


class StructureClientUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'une structure cliente."""

    class Meta:
        model = StructureClient
        fields = [
            'nom', 'adresse', 'telephone',
            'contact_principal', 'email_facturation', 'logo', 'logo_url', 'actif'
        ]


# ==============================================================================
# SERIALIZERS CLIENT (Utilisateur d'une Structure)
# ==============================================================================

class ClientLightSerializer(serializers.ModelSerializer):
    """Serializer léger pour les utilisateurs clients (sans détails structure)."""
    email = serializers.EmailField(source='utilisateur.email', read_only=True)
    nom = serializers.CharField(source='utilisateur.nom', read_only=True)
    prenom = serializers.CharField(source='utilisateur.prenom', read_only=True)
    actif = serializers.BooleanField(source='utilisateur.actif', read_only=True)

    class Meta:
        model = Client
        fields = [
            'utilisateur', 'email', 'nom', 'prenom', 'actif'
        ]


class ClientSerializer(serializers.ModelSerializer):
    """Serializer pour les clients avec leur structure."""
    utilisateur_detail = UtilisateurSerializer(source='utilisateur', read_only=True)
    email = serializers.EmailField(source='utilisateur.email', read_only=True)
    nom = serializers.CharField(source='utilisateur.nom', read_only=True)
    prenom = serializers.CharField(source='utilisateur.prenom', read_only=True)
    actif = serializers.BooleanField(source='utilisateur.actif', read_only=True)
    # Retourne l'objet structure complet (pas juste l'ID)
    structure = StructureClientSerializer(read_only=True)
    structure_id = serializers.PrimaryKeyRelatedField(
        queryset=StructureClient.objects.all(),
        source='structure',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = Client
        fields = [
            'utilisateur', 'utilisateur_detail', 'email', 'nom', 'prenom', 'actif',
            'structure', 'structure_id',
            # Legacy fields (for backward compatibility)
            'nom_structure', 'adresse', 'telephone',
            'contact_principal', 'email_facturation', 'logo'
        ]
        read_only_fields = ['utilisateur']


class ClientCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un utilisateur client dans une structure."""
    email = serializers.EmailField(write_only=True)
    nom = serializers.CharField(write_only=True)
    prenom = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])
    structure_id = serializers.PrimaryKeyRelatedField(
        queryset=StructureClient.objects.all(),
        source='structure',
        required=True
    )

    class Meta:
        model = Client
        fields = [
            'email', 'nom', 'prenom', 'password', 'structure_id'
        ]

    def create(self, validated_data):
        # Extraire les données utilisateur
        user_data = {
            'email': validated_data.pop('email'),
            'nom': validated_data.pop('nom'),
            'prenom': validated_data.pop('prenom'),
        }
        password = validated_data.pop('password')

        # Créer l'utilisateur
        utilisateur = Utilisateur.objects.create_user(
            password=password,
            **user_data
        )

        # Créer le profil client lié à la structure
        client = Client.objects.create(
            utilisateur=utilisateur,
            **validated_data
        )

        # Attribuer automatiquement le rôle CLIENT
        from .models import Role, UtilisateurRole
        role_client, _ = Role.objects.get_or_create(nom_role='CLIENT')
        UtilisateurRole.objects.get_or_create(
            utilisateur=utilisateur,
            role=role_client
        )

        return client


class ClientWithStructureCreateSerializer(serializers.Serializer):
    """
    Serializer pour créer une structure ET son premier utilisateur en une seule requête.
    Utile pour la rétro-compatibilité avec l'ancien flux de création de client.
    """
    # Données utilisateur
    email = serializers.EmailField()
    nom = serializers.CharField()
    prenom = serializers.CharField()
    password = serializers.CharField(validators=[validate_password])

    # Données structure
    nom_structure = serializers.CharField()
    adresse = serializers.CharField(required=False, allow_blank=True, default='')
    telephone = serializers.CharField(required=False, allow_blank=True, default='')
    contact_principal = serializers.CharField(required=False, allow_blank=True, default='')
    email_facturation = serializers.EmailField(required=False, allow_blank=True, default='')
    logo = serializers.URLField(required=False, allow_null=True, default=None)

    def create(self, validated_data):
        # Extraire les données
        user_data = {
            'email': validated_data['email'],
            'nom': validated_data['nom'],
            'prenom': validated_data['prenom'],
        }
        password = validated_data['password']

        structure_data = {
            'nom': validated_data['nom_structure'],
            'adresse': validated_data.get('adresse', ''),
            'telephone': validated_data.get('telephone', ''),
            'contact_principal': validated_data.get('contact_principal', ''),
            'email_facturation': validated_data.get('email_facturation', ''),
            'logo': validated_data.get('logo'),
        }

        # Créer la structure
        structure = StructureClient.objects.create(**structure_data)

        # Créer l'utilisateur
        utilisateur = Utilisateur.objects.create_user(
            password=password,
            **user_data
        )

        # Créer le profil client lié à la structure
        client = Client.objects.create(
            utilisateur=utilisateur,
            structure=structure,
            nom_structure=structure.nom  # Legacy field
        )

        # Attribuer automatiquement le rôle CLIENT
        from .models import Role, UtilisateurRole
        role_client, _ = Role.objects.get_or_create(nom_role='CLIENT')
        UtilisateurRole.objects.get_or_create(
            utilisateur=utilisateur,
            role=role_client
        )

        return client


# ==============================================================================
# SERIALIZERS SUPERVISEUR
# ==============================================================================

class SuperviseurSerializer(serializers.ModelSerializer):
    """
    Serializer pour les superviseurs.

    ⚠️ NOUVEAU (Refactorisation Architecture RH)
    Le superviseur est un utilisateur qui se connecte et gère les équipes.
    """
    utilisateur_detail = UtilisateurSerializer(source='utilisateur', read_only=True)
    email = serializers.EmailField(source='utilisateur.email', read_only=True)
    nom = serializers.CharField(source='utilisateur.nom', read_only=True)
    prenom = serializers.CharField(source='utilisateur.prenom', read_only=True)
    full_name = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    actif = serializers.BooleanField(source='utilisateur.actif', read_only=True)

    # Propriétés calculées
    nombre_equipes = serializers.IntegerField(read_only=True)
    nombre_operateurs = serializers.IntegerField(read_only=True)

    class Meta:
        model = Superviseur
        fields = [
            'utilisateur', 'utilisateur_detail', 'email', 'nom', 'prenom', 'full_name', 'actif',
            'matricule', 'secteur_geographique', 'telephone', 'date_prise_fonction',
            'nombre_equipes', 'nombre_operateurs'
        ]
        read_only_fields = ['utilisateur', 'nombre_equipes', 'nombre_operateurs']


class SuperviseurCreateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la création d'un superviseur avec son utilisateur.

    Crée automatiquement :
    1. Un compte utilisateur
    2. Un profil superviseur
    3. Attribue le rôle SUPERVISEUR
    """
    # Champs utilisateur
    email = serializers.EmailField(write_only=True)
    nom = serializers.CharField(write_only=True)
    prenom = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = Superviseur
        fields = [
            'email', 'nom', 'prenom', 'password',
            'matricule', 'secteur_geographique', 'telephone', 'date_prise_fonction'
        ]

    def create(self, validated_data):
        # Extraire les données utilisateur
        user_data = {
            'email': validated_data.pop('email'),
            'nom': validated_data.pop('nom'),
            'prenom': validated_data.pop('prenom'),
        }
        password = validated_data.pop('password')

        # Créer l'utilisateur
        utilisateur = Utilisateur.objects.create_user(
            password=password,
            **user_data
        )

        # Créer le profil superviseur
        superviseur = Superviseur.objects.create(
            utilisateur=utilisateur,
            **validated_data
        )

        # Attribuer automatiquement le rôle SUPERVISEUR
        from .models import Role, UtilisateurRole
        role_superviseur, _ = Role.objects.get_or_create(nom_role='SUPERVISEUR')
        UtilisateurRole.objects.get_or_create(
            utilisateur=utilisateur,
            role=role_superviseur
        )

        return superviseur


class SuperviseurUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'un superviseur."""

    class Meta:
        model = Superviseur
        fields = ['matricule', 'secteur_geographique', 'telephone', 'date_prise_fonction']


# ==============================================================================
# SERIALIZERS COMPETENCE
# ==============================================================================

class CompetenceSerializer(serializers.ModelSerializer):
    """Serializer pour les compétences."""
    categorie_display = serializers.CharField(source='get_categorie_display', read_only=True)

    class Meta:
        model = Competence
        fields = [
            'id', 'nom_competence', 'categorie', 'categorie_display',
            'description', 'ordre_affichage'
        ]


class CompetenceOperateurSerializer(serializers.ModelSerializer):
    """Serializer pour les compétences d'un opérateur."""
    competence_detail = CompetenceSerializer(source='competence', read_only=True)
    niveau_display = serializers.CharField(source='get_niveau_display', read_only=True)
    operateur_nom = serializers.CharField(source='operateur.nom_complet', read_only=True)

    class Meta:
        model = CompetenceOperateur
        fields = [
            'id', 'operateur', 'operateur_nom', 'competence', 'competence_detail',
            'niveau', 'niveau_display', 'date_acquisition', 'date_modification'
        ]
        read_only_fields = ['date_modification']


class CompetenceOperateurUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour du niveau de compétence."""

    class Meta:
        model = CompetenceOperateur
        fields = ['niveau', 'date_acquisition']


# ==============================================================================
# SERIALIZERS OPERATEUR
# ==============================================================================

class OperateurListSerializer(serializers.ModelSerializer):
    """
    Serializer pour la liste des opérateurs (vue simplifiée).

    ⚠️ REFACTORISATION : Operateur est maintenant standalone (pas de lien utilisateur).
    """
    full_name = serializers.CharField(source='nom_complet', read_only=True)
    equipe_nom = serializers.CharField(source='equipe.nom_equipe', read_only=True, allow_null=True)
    superviseur_nom = serializers.CharField(source='superviseur.utilisateur.get_full_name', read_only=True, allow_null=True)
    est_chef_equipe = serializers.BooleanField(read_only=True)
    est_disponible = serializers.BooleanField(read_only=True)
    peut_etre_chef = serializers.SerializerMethodField()

    class Meta:
        model = Operateur
        fields = [
            'id', 'actif', 'nom', 'prenom', 'full_name', 'email',
            'numero_immatriculation', 'statut', 'equipe', 'equipe_nom',
            'superviseur', 'superviseur_nom',
            'date_embauche', 'date_sortie', 'telephone', 'photo',
            'est_chef_equipe', 'est_disponible', 'peut_etre_chef'
        ]

    def get_peut_etre_chef(self, obj):
        """Retourne True si l'opérateur a la compétence 'Gestion d'équipe'."""
        return obj.peut_etre_chef()


class OperateurDetailSerializer(serializers.ModelSerializer):
    """
    Serializer détaillé pour un opérateur.

    ⚠️ REFACTORISATION : Operateur est maintenant standalone (pas de lien utilisateur).
    """
    full_name = serializers.CharField(source='nom_complet', read_only=True)
    equipe_nom = serializers.CharField(source='equipe.nom_equipe', read_only=True, allow_null=True)
    superviseur_detail = SuperviseurSerializer(source='superviseur', read_only=True)
    competences_detail = CompetenceOperateurSerializer(
        source='competences_operateur',
        many=True,
        read_only=True
    )
    est_chef_equipe = serializers.BooleanField(read_only=True)
    est_disponible = serializers.BooleanField(read_only=True)
    peut_etre_chef = serializers.SerializerMethodField()

    class Meta:
        model = Operateur
        fields = [
            'id', 'nom', 'prenom', 'full_name', 'email',
            'numero_immatriculation', 'statut', 'equipe', 'equipe_nom',
            'superviseur', 'superviseur_detail',
            'date_embauche', 'date_sortie', 'telephone', 'photo',
            'competences_detail',
            'est_chef_equipe', 'est_disponible', 'peut_etre_chef'
        ]

    def get_peut_etre_chef(self, obj):
        return obj.peut_etre_chef()


class OperateurCreateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la création d'un opérateur (DONNÉE RH).

    ⚠️ REFACTORISATION : Operateur ne crée PLUS de compte utilisateur.
    C'est une simple donnée RH gérée par les superviseurs/admins.
    """

    class Meta:
        model = Operateur
        fields = [
            'nom', 'prenom', 'email',
            'numero_immatriculation', 'statut', 'equipe', 'superviseur',
            'date_embauche', 'date_sortie', 'telephone', 'photo'
        ]

    def create(self, validated_data):
        # Créer l'opérateur (standalone, pas d'utilisateur)
        operateur = Operateur.objects.create(**validated_data)

        # Historiser l'affectation à l'équipe si applicable
        if operateur.equipe:
            HistoriqueEquipeOperateur.objects.create(
                operateur=operateur,
                equipe=operateur.equipe,
                date_debut=timezone.now().date(),
                role_dans_equipe='MEMBRE'
            )

        return operateur


class OperateurUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la mise à jour d'un opérateur.

    ⚠️ REFACTORISATION : Operateur est standalone, mise à jour directe des champs.
    """

    class Meta:
        model = Operateur
        fields = [
            'nom', 'prenom', 'email',
            'numero_immatriculation', 'statut', 'equipe', 'superviseur',
            'date_sortie', 'telephone', 'photo'
        ]

    def update(self, instance, validated_data):
        # Gérer le changement d'équipe pour l'historique
        old_equipe = instance.equipe
        new_equipe = validated_data.get('equipe', old_equipe)

        if old_equipe != new_equipe:
            # Fermer l'ancien historique
            if old_equipe:
                HistoriqueEquipeOperateur.objects.filter(
                    operateur=instance,
                    equipe=old_equipe,
                    date_fin__isnull=True
                ).update(date_fin=timezone.now().date())

            # Créer le nouvel historique
            if new_equipe:
                HistoriqueEquipeOperateur.objects.create(
                    operateur=instance,
                    equipe=new_equipe,
                    date_debut=timezone.now().date(),
                    role_dans_equipe='MEMBRE'
                )

        # Mettre à jour l'opérateur
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        return instance


# ==============================================================================
# SERIALIZERS EQUIPE
# ==============================================================================

class EquipeListSerializer(serializers.ModelSerializer):
    """
    ⚡ Serializer OPTIMISÉ pour la liste des équipes.

    Désactive tous les champs calculés coûteux pour accélérer le chargement (22s → <1s).
    Les détails complets sont disponibles via EquipeDetailSerializer (retrieve).
    """
    chef_equipe_nom = serializers.CharField(
        source='chef_equipe.nom_complet',
        read_only=True,
        allow_null=True
    )

    # ✅ Multi-site architecture: site principal
    site_principal_nom = serializers.CharField(
        source='site_principal.nom_site',
        read_only=True,
        allow_null=True
    )

    # ⚠️ DÉSACTIVÉ: Ces champs font des requêtes N+1 (réactivés dans DetailSerializer)
    # statut_operationnel = serializers.CharField(read_only=True)  # Property avec query
    # superviseur_nom = ...  # SerializerMethodField avec query
    # sites_secondaires_noms = ...  # .all() sur chaque équipe
    # tous_les_sites = ...  # Property avec queries

    # ✅ RÉACTIVÉ avec annotation pour éviter N+1 queries
    nombre_membres = serializers.IntegerField(source='nombre_membres_count', read_only=True, default=0)

    class Meta:
        model = Equipe
        fields = [
            'id', 'nom_equipe',
            'chef_equipe', 'chef_equipe_nom',
            'site_principal', 'site_principal_nom',  # ✅ Multi-site architecture
            'actif', 'date_creation',
            'nombre_membres',  # ✅ Ajouté (utilisé annotation pour perf)
            # Champs désactivés pour performance, voir EquipeDetailSerializer
        ]


class EquipeDetailSerializer(serializers.ModelSerializer):
    """
    Serializer détaillé pour une équipe.

    ⚠️ REFACTORISATION (Multi-Sites) :
    - Le superviseur est déduit du site principal (propriété calculée)
    - Une équipe peut avoir un site principal + sites secondaires
    """
    chef_equipe_detail = OperateurListSerializer(source='chef_equipe', read_only=True)
    chef_equipe_nom = serializers.CharField(
        source='chef_equipe.nom_complet',
        read_only=True,
        allow_null=True
    )
    superviseur_detail = serializers.SerializerMethodField(read_only=True)
    superviseur = serializers.SerializerMethodField(read_only=True)
    superviseur_nom = serializers.SerializerMethodField(read_only=True)

    # ✅ NOUVEAU : Champs multi-sites
    site_principal_nom = serializers.CharField(
        source='site_principal.nom_site',
        read_only=True,
        allow_null=True
    )
    sites_secondaires_noms = serializers.SerializerMethodField(read_only=True)
    tous_les_sites = serializers.SerializerMethodField(read_only=True)

    # ⚠️ LEGACY : Ancien champ conservé temporairement
    site_nom = serializers.CharField(source='site.nom_site', read_only=True, allow_null=True)

    membres = OperateurListSerializer(source='operateurs', many=True, read_only=True)
    nombre_membres = serializers.IntegerField(read_only=True)
    statut_operationnel = serializers.CharField(read_only=True)

    def get_superviseur_detail(self, obj):
        """Retourne les détails du superviseur (déduit du site principal)."""
        if obj.superviseur:
            return SuperviseurSerializer(obj.superviseur).data
        return None

    def get_superviseur(self, obj):
        """Retourne l'ID du superviseur (déduit du site principal)."""
        return obj.superviseur.utilisateur_id if obj.superviseur else None

    def get_superviseur_nom(self, obj):
        """Retourne le nom complet du superviseur (déduit du site principal)."""
        if obj.superviseur and hasattr(obj.superviseur, 'utilisateur'):
            return obj.superviseur.utilisateur.get_full_name()
        return None

    def get_sites_secondaires_noms(self, obj):
        """Retourne la liste des noms des sites secondaires."""
        return [site.nom_site for site in obj.sites_secondaires.all()]

    def get_tous_les_sites(self, obj):
        """Retourne tous les sites (principal + secondaires) avec détails complets."""
        sites = []
        for site in obj.tous_les_sites:
            sites.append({
                'id': site.id,
                'nom': site.nom_site,
                'code': site.code_site if hasattr(site, 'code_site') else None
            })
        return sites

    class Meta:
        model = Equipe
        fields = [
            'id', 'nom_equipe',
            'chef_equipe', 'chef_equipe_detail', 'chef_equipe_nom',
            'superviseur', 'superviseur_detail', 'superviseur_nom',
            # Nouveaux champs multi-sites
            'site_principal', 'site_principal_nom',
            'sites_secondaires', 'sites_secondaires_noms',
            'tous_les_sites',
            # Legacy
            'site', 'site_nom',
            'actif', 'date_creation',
            'nombre_membres', 'statut_operationnel', 'membres'
        ]


class EquipeCreateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la création d'une équipe.

    ⚠️ REFACTORISATION (Multi-Sites) :
    - Le superviseur est déduit automatiquement du site principal
    - Possibilité d'affecter plusieurs sites secondaires
    """
    membres = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Operateur.objects.all(),
        required=False,
        write_only=True
    )
    sites_secondaires = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Site.objects.all(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = Equipe
        fields = [
            'id', 'nom_equipe', 'chef_equipe',
            'site_principal', 'sites_secondaires',
            'site',  # Legacy, optionnel
            'actif', 'membres'
        ]
        read_only_fields = ['id']

    def validate_chef_equipe(self, value):
        """Vérifie que le chef a la compétence requise."""
        # Si aucune valeur fournie (chef optionnel), accepter
        if value is None:
            return value

        if not value.peut_etre_chef():
            raise serializers.ValidationError(
                "Cet opérateur ne peut pas être chef d'équipe. "
                "Il doit avoir la compétence 'Gestion d'équipe' "
                "avec un niveau Intermédiaire ou Expert."
            )
        return value

    def create(self, validated_data):
        membres = validated_data.pop('membres', [])
        sites_secondaires = validated_data.pop('sites_secondaires', [])

        # Créer l'équipe (skip_validation car on a déjà validé)
        equipe = Equipe.objects.create(**validated_data)

        # Affecter les sites secondaires
        if sites_secondaires:
            equipe.sites_secondaires.set(sites_secondaires)

        # Affecter les membres à l'équipe
        today = timezone.now().date()
        for membre in membres:
            membre.equipe = equipe
            membre.save()

            # Historiser l'affectation
            HistoriqueEquipeOperateur.objects.create(
                operateur=membre,
                equipe=equipe,
                date_debut=today,
                role_dans_equipe='MEMBRE'
            )

        return equipe


class EquipeUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer pour la mise à jour d'une équipe.

    ⚠️ REFACTORISATION (Multi-Sites) :
    - Le superviseur est déduit automatiquement du site principal (non modifiable directement)
    - Possibilité de modifier les sites secondaires
    """
    sites_secondaires = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Site.objects.all(),
        required=False,
        allow_empty=True
    )

    class Meta:
        model = Equipe
        fields = [
            'nom_equipe', 'chef_equipe',
            'site_principal', 'sites_secondaires',
            'site',  # Legacy, optionnel
            'actif'
        ]

    def validate_chef_equipe(self, value):
        """Vérifie que le chef a la compétence requise."""
        if value is None:
            return value

        if not value.peut_etre_chef():
            raise serializers.ValidationError(
                "Cet opérateur ne peut pas être chef d'équipe. "
                "Il doit avoir la compétence 'Gestion d'équipe' "
                "avec un niveau Intermédiaire ou Expert."
            )
        return value

    def update(self, instance, validated_data):
        """Met à jour l'équipe."""
        sites_secondaires = validated_data.pop('sites_secondaires', None)

        # Mettre à jour les champs simples
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Mettre à jour les sites secondaires si fournis
        if sites_secondaires is not None:
            instance.sites_secondaires.set(sites_secondaires)

        return instance


class AffecterMembresSerializer(serializers.Serializer):
    """Serializer pour affecter des membres à une équipe.

    Accepte une liste d'IDs (entiers). Pour chaque ID :
    - si un `Operateur` existe avec cette PK, on l'utilise
    - sinon si un `Utilisateur` existe, on crée un `Operateur` minimal
      (numéro d'immatriculation auto-généré, date_embauche = aujourd'hui)
      afin de permettre à des administrateurs (ou utilisateurs avec rôle)
      d'être ajoutés comme membres même s'ils n'avaient pas de profil
      opérateur préalable.
    """
    operateurs = serializers.ListField(child=serializers.IntegerField())

    def validate_operateurs(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('La valeur doit être une liste d\'IDs.')
        return value

    def update_membres(self, equipe, operateurs):
        today = timezone.now().date()

        # Convertir les IDs en objets Operateur, en créant si nécessaire
        operateur_objs = []
        for pk in operateurs:
            try:
                op = Operateur.objects.get(pk=pk)
            except Operateur.DoesNotExist:
                try:
                    user = Utilisateur.objects.get(pk=pk)
                except Utilisateur.DoesNotExist:
                    raise serializers.ValidationError({'operateurs': f'Utilisateur {pk} inexistant.'})

                # Générer un numéro d'immatriculation unique
                base_num = f'AUTO-{user.id}'
                numero = base_num
                suffix = 1
                while Operateur.objects.filter(numero_immatriculation=numero).exists():
                    suffix += 1
                    numero = f"{base_num}-{suffix}"

                op = Operateur.objects.create(
                    utilisateur=user,
                    numero_immatriculation=numero,
                    date_embauche=today,
                    telephone=''
                )
            operateur_objs.append(op)

        # Retirer les anciens membres
        anciens_membres = equipe.operateurs.all()
        for ancien in anciens_membres:
            if ancien not in operateur_objs:
                # Fermer l'historique
                HistoriqueEquipeOperateur.objects.filter(
                    operateur=ancien,
                    equipe=equipe,
                    date_fin__isnull=True
                ).update(date_fin=today)

                ancien.equipe = None
                ancien.save()

        # Ajouter les nouveaux membres
        for nouveau in operateur_objs:
            if nouveau.equipe != equipe:
                # Fermer l'ancien historique si existant
                if nouveau.equipe:
                    HistoriqueEquipeOperateur.objects.filter(
                        operateur=nouveau,
                        equipe=nouveau.equipe,
                        date_fin__isnull=True
                    ).update(date_fin=today)

                # Créer le nouvel historique
                HistoriqueEquipeOperateur.objects.create(
                    operateur=nouveau,
                    equipe=equipe,
                    date_debut=today,
                    role_dans_equipe='MEMBRE'
                )

                nouveau.equipe = equipe
                nouveau.save()

        return equipe


# ==============================================================================
# SERIALIZERS HORAIRE TRAVAIL (PHASE 2)
# ==============================================================================

class HoraireTravailSerializer(serializers.ModelSerializer):
    """
    Serializer pour les horaires de travail.

    ✅ PHASE 2: Permet de définir les horaires de travail globaux ou par équipe.
    - equipe = null : Configuration globale (par défaut pour toutes les équipes)
    - equipe = ID : Configuration spécifique à une équipe
    """
    equipe_nom = serializers.SerializerMethodField()
    jour_semaine_display = serializers.CharField(
        source='get_jour_semaine_display',
        read_only=True
    )
    heures_travaillables = serializers.FloatField(read_only=True)

    def get_equipe_nom(self, obj):
        """Retourne le nom de l'équipe ou 'Configuration Globale' si equipe est null."""
        return obj.equipe.nom_equipe if obj.equipe else "Configuration Globale"

    class Meta:
        model = HoraireTravail
        fields = [
            'id', 'equipe', 'equipe_nom',
            'jour_semaine', 'jour_semaine_display',
            'heure_debut', 'heure_fin',
            'duree_pause_minutes', 'actif',
            'heures_travaillables'
        ]
        read_only_fields = ['id', 'heures_travaillables']


class HoraireTravailCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un horaire de travail."""

    class Meta:
        model = HoraireTravail
        fields = [
            'equipe', 'jour_semaine',
            'heure_debut', 'heure_fin',
            'duree_pause_minutes', 'actif'
        ]

    def validate(self, attrs):
        """Valide que l'heure de fin est après l'heure de début."""
        if attrs['heure_fin'] <= attrs['heure_debut']:
            raise serializers.ValidationError({
                'heure_fin': "L'heure de fin doit être postérieure à l'heure de début."
            })

        # Vérifier qu'il n'existe pas déjà un horaire actif pour cette équipe et ce jour
        equipe = attrs['equipe']
        jour = attrs['jour_semaine']

        existing = HoraireTravail.objects.filter(
            equipe=equipe,
            jour_semaine=jour,
            actif=True
        )

        if existing.exists():
            raise serializers.ValidationError(
                f"Un horaire actif existe déjà pour {equipe.nom_equipe} le {jour}. "
                "Désactivez-le d'abord avant d'en créer un nouveau."
            )

        return attrs


class HoraireTravailUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'un horaire de travail."""

    class Meta:
        model = HoraireTravail
        fields = [
            'heure_debut', 'heure_fin',
            'duree_pause_minutes', 'actif'
        ]

    def validate(self, attrs):
        """Valide que l'heure de fin est après l'heure de début."""
        instance = self.instance
        heure_debut = attrs.get('heure_debut', instance.heure_debut)
        heure_fin = attrs.get('heure_fin', instance.heure_fin)

        if heure_fin <= heure_debut:
            raise serializers.ValidationError({
                'heure_fin': "L'heure de fin doit être postérieure à l'heure de début."
            })

        return attrs


# ==============================================================================
# SERIALIZERS JOUR FERIE (PHASE 3)
# ==============================================================================

class JourFerieSerializer(serializers.ModelSerializer):
    """
    Serializer pour les jours fériés.

    ✅ PHASE 3: Permet de gérer les jours fériés nationaux et locaux.
    """
    type_ferie_display = serializers.CharField(source='get_type_ferie_display', read_only=True)

    class Meta:
        model = JourFerie
        fields = [
            'id', 'nom', 'date',
            'type_ferie', 'type_ferie_display',
            'recurrent', 'description', 'actif'
        ]
        read_only_fields = ['id']


class JourFerieCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un jour férié."""

    class Meta:
        model = JourFerie
        fields = ['nom', 'date', 'type_ferie', 'recurrent', 'description', 'actif']

    def validate(self, attrs):
        """Validation pour éviter doublons sur même date+type."""
        nom = attrs.get('nom')
        date = attrs.get('date')
        type_ferie = attrs.get('type_ferie')

        # Vérifier que le nom n'est pas vide
        if not nom or not nom.strip():
            raise serializers.ValidationError({
                'nom': "Le nom du jour férié est requis."
            })

        # Vérifier doublon uniquement à la création (pas d'instance existante)
        if not self.instance:
            existing = JourFerie.objects.filter(
                date=date,
                type_ferie=type_ferie
            ).exists()

            if existing:
                raise serializers.ValidationError(
                    f"Un jour férié de type '{type_ferie}' existe déjà pour la date {date.strftime('%d/%m/%Y')}."
                )

        return attrs


class JourFerieUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'un jour férié."""

    class Meta:
        model = JourFerie
        fields = ['nom', 'type_ferie', 'recurrent', 'description', 'actif']


# ==============================================================================
# SERIALIZERS ABSENCE
# ==============================================================================

class AbsenceSerializer(serializers.ModelSerializer):
    """Serializer pour les absences."""
    operateur_nom = serializers.CharField(
        source='operateur.nom_complet',
        read_only=True
    )
    type_absence_display = serializers.CharField(
        source='get_type_absence_display',
        read_only=True
    )
    statut_display = serializers.CharField(
        source='get_statut_display',
        read_only=True
    )
    validee_par_nom = serializers.CharField(
        source='validee_par.get_full_name',
        read_only=True,
        allow_null=True
    )
    duree_jours = serializers.IntegerField(read_only=True)
    equipe_impactee = serializers.SerializerMethodField()

    class Meta:
        model = Absence
        fields = [
            'id', 'operateur', 'operateur_nom',
            'type_absence', 'type_absence_display',
            'date_debut', 'date_fin', 'duree_jours',
            'statut', 'statut_display',
            'motif', 'date_demande',
            'validee_par', 'validee_par_nom', 'date_validation',
            'commentaire', 'equipe_impactee'
        ]
        read_only_fields = ['date_demande', 'date_validation']

    def get_equipe_impactee(self, obj):
        """Retourne le nom de l'équipe impactée si l'absence est validée."""
        if obj.statut == StatutAbsence.VALIDEE and obj.operateur.equipe:
            return {
                'id': obj.operateur.equipe.id,
                'nom': obj.operateur.equipe.nom_equipe
            }
        return None


class AbsenceCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'une absence."""

    class Meta:
        model = Absence
        fields = [
            'operateur', 'type_absence', 'date_debut', 'date_fin', 'motif'
        ]

    def validate(self, attrs):
        """Validation des dates et chevauchements."""
        if attrs['date_fin'] < attrs['date_debut']:
            raise serializers.ValidationError({
                'date_fin': "La date de fin doit être postérieure à la date de début."
            })

        # Vérifier le chevauchement
        chevauchement = Absence.objects.filter(
            operateur=attrs['operateur'],
            statut__in=[StatutAbsence.DEMANDEE, StatutAbsence.VALIDEE],
            date_debut__lte=attrs['date_fin'],
            date_fin__gte=attrs['date_debut']
        )

        if chevauchement.exists():
            raise serializers.ValidationError(
                "Cette période chevauche une autre absence existante."
            )

        return attrs

    def create(self, validated_data):
        current_user = validated_data.pop('_current_user', None)
        instance = super().create(validated_data)
        if current_user:
            instance._current_user = current_user
        return instance


class AbsenceValidationSerializer(serializers.Serializer):
    """Serializer pour valider/refuser une absence."""
    action = serializers.ChoiceField(choices=['valider', 'refuser'])
    commentaire = serializers.CharField(required=False, allow_blank=True)

    def update_absence(self, absence, user, _current_user=None):
        """Met à jour le statut de l'absence."""
        action = self.validated_data['action']
        commentaire = self.validated_data.get('commentaire', '')

        if action == 'valider':
            absence.statut = StatutAbsence.VALIDEE
        else:
            absence.statut = StatutAbsence.REFUSEE

        absence.validee_par = user
        absence.date_validation = timezone.now()
        absence.commentaire = commentaire
        
        if _current_user:
            absence._current_user = _current_user
            
        absence.save()

        return absence


# ==============================================================================
# SERIALIZERS HISTORIQUE
# ==============================================================================

class HistoriqueEquipeOperateurSerializer(serializers.ModelSerializer):
    """Serializer pour l'historique des équipes."""
    operateur_nom = serializers.CharField(
        source='operateur.nom_complet',
        read_only=True
    )
    equipe_nom = serializers.CharField(
        source='equipe.nom_equipe',
        read_only=True
    )

    class Meta:
        model = HistoriqueEquipeOperateur
        fields = [
            'id', 'operateur', 'operateur_nom',
            'equipe', 'equipe_nom',
            'date_debut', 'date_fin', 'role_dans_equipe'
        ]


# ==============================================================================
# SERIALIZERS POUR FILTRAGE OPERATEURS PAR COMPETENCE
# ==============================================================================

class OperateurParCompetenceSerializer(serializers.Serializer):
    """Serializer pour le filtrage d'opérateurs par compétence."""
    competence_id = serializers.IntegerField(required=False)
    competence_nom = serializers.CharField(required=False)
    niveau_minimum = serializers.ChoiceField(
        choices=NiveauCompetence.choices,
        required=False
    )
    disponible_uniquement = serializers.BooleanField(default=False)
