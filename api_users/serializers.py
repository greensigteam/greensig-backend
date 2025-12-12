# api_users/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import (
    Utilisateur, Role, UtilisateurRole, Client, Operateur,
    Competence, CompetenceOperateur, Equipe, Absence,
    HistoriqueEquipeOperateur, TypeUtilisateur, StatutOperateur,
    NiveauCompetence, StatutAbsence
)


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
            'type_utilisateur', 'date_creation', 'actif',
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
            'type_utilisateur', 'actif'
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
# SERIALIZERS CLIENT
# ==============================================================================

class ClientSerializer(serializers.ModelSerializer):
    """Serializer pour les clients."""
    utilisateur_detail = UtilisateurSerializer(source='utilisateur', read_only=True)
    email = serializers.EmailField(source='utilisateur.email', read_only=True)
    nom = serializers.CharField(source='utilisateur.nom', read_only=True)
    prenom = serializers.CharField(source='utilisateur.prenom', read_only=True)
    actif = serializers.BooleanField(source='utilisateur.actif', read_only=True)

    class Meta:
        model = Client
        fields = [
            'utilisateur', 'utilisateur_detail', 'email', 'nom', 'prenom', 'actif',
            'nom_structure', 'adresse', 'telephone',
            'contact_principal', 'email_facturation', 'logo'
        ]
        read_only_fields = ['utilisateur']


class ClientCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un client avec son utilisateur."""
    email = serializers.EmailField(write_only=True)
    nom = serializers.CharField(write_only=True)
    prenom = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = Client
        fields = [
            'email', 'nom', 'prenom', 'password',
            'nom_structure', 'adresse', 'telephone',
            'contact_principal', 'email_facturation', 'logo'
        ]

    def create(self, validated_data):
        # Extraire les données utilisateur
        user_data = {
            'email': validated_data.pop('email'),
            'nom': validated_data.pop('nom'),
            'prenom': validated_data.pop('prenom'),
            'type_utilisateur': TypeUtilisateur.CLIENT,
        }
        password = validated_data.pop('password')

        # Créer l'utilisateur
        utilisateur = Utilisateur.objects.create_user(
            password=password,
            **user_data
        )

        # Créer le profil client
        client = Client.objects.create(
            utilisateur=utilisateur,
            **validated_data
        )

        # Attribuer le rôle CLIENT
        role_client, _ = Role.objects.get_or_create(nom_role='CLIENT')
        UtilisateurRole.objects.create(utilisateur=utilisateur, role=role_client)

        return client


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
    operateur_nom = serializers.CharField(source='operateur.utilisateur.get_full_name', read_only=True)

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
    """Serializer pour la liste des opérateurs (vue simplifiée)."""
    email = serializers.EmailField(source='utilisateur.email', read_only=True)
    nom = serializers.CharField(source='utilisateur.nom', read_only=True)
    prenom = serializers.CharField(source='utilisateur.prenom', read_only=True)
    full_name = serializers.CharField(source='utilisateur.get_full_name', read_only=True)
    actif = serializers.BooleanField(source='utilisateur.actif', read_only=True)
    equipe_nom = serializers.CharField(source='equipe.nom_equipe', read_only=True, allow_null=True)
    est_chef_equipe = serializers.BooleanField(read_only=True)
    est_disponible = serializers.BooleanField(read_only=True)

    class Meta:
        model = Operateur
        fields = [
            'utilisateur', 'email', 'nom', 'prenom', 'full_name', 'actif',
            'numero_immatriculation', 'statut', 'equipe', 'equipe_nom',
            'date_embauche', 'telephone', 'photo',
            'est_chef_equipe', 'est_disponible'
        ]


class OperateurDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un opérateur."""
    utilisateur_detail = UtilisateurSerializer(source='utilisateur', read_only=True)
    email = serializers.EmailField(source='utilisateur.email', read_only=True)
    nom = serializers.CharField(source='utilisateur.nom', read_only=True)
    prenom = serializers.CharField(source='utilisateur.prenom', read_only=True)
    actif = serializers.BooleanField(source='utilisateur.actif', read_only=True)
    equipe_nom = serializers.CharField(source='equipe.nom_equipe', read_only=True, allow_null=True)
    competences_detail = CompetenceOperateurSerializer(
        source='competences_operateur',
        many=True,
        read_only=True
    )
    equipes_dirigees_count = serializers.SerializerMethodField()
    est_chef_equipe = serializers.BooleanField(read_only=True)
    est_disponible = serializers.BooleanField(read_only=True)
    peut_etre_chef = serializers.SerializerMethodField()

    class Meta:
        model = Operateur
        fields = [
            'utilisateur', 'utilisateur_detail', 'email', 'nom', 'prenom', 'actif',
            'numero_immatriculation', 'statut', 'equipe', 'equipe_nom',
            'date_embauche', 'telephone', 'photo',
            'competences_detail', 'equipes_dirigees_count',
            'est_chef_equipe', 'est_disponible', 'peut_etre_chef'
        ]

    def get_equipes_dirigees_count(self, obj):
        return obj.equipes_dirigees.filter(actif=True).count()

    def get_peut_etre_chef(self, obj):
        return obj.peut_etre_chef()


class OperateurCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'un opérateur avec son utilisateur."""
    email = serializers.EmailField(write_only=True)
    nom = serializers.CharField(write_only=True)
    prenom = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = Operateur
        fields = [
            'email', 'nom', 'prenom', 'password',
            'numero_immatriculation', 'statut', 'equipe',
            'date_embauche', 'telephone', 'photo'
        ]

    def create(self, validated_data):
        # Extraire les données utilisateur
        user_data = {
            'email': validated_data.pop('email'),
            'nom': validated_data.pop('nom'),
            'prenom': validated_data.pop('prenom'),
            'type_utilisateur': TypeUtilisateur.OPERATEUR,
        }
        password = validated_data.pop('password')

        # Créer l'utilisateur
        utilisateur = Utilisateur.objects.create_user(
            password=password,
            **user_data
        )

        # Créer le profil opérateur
        operateur = Operateur.objects.create(
            utilisateur=utilisateur,
            **validated_data
        )

        # Attribuer le rôle OPERATEUR
        role_operateur, _ = Role.objects.get_or_create(nom_role='OPERATEUR')
        UtilisateurRole.objects.create(utilisateur=utilisateur, role=role_operateur)

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
    """Serializer pour la mise à jour d'un opérateur."""
    nom = serializers.CharField(write_only=True, required=False)
    prenom = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True, required=False)
    actif = serializers.BooleanField(write_only=True, required=False)

    class Meta:
        model = Operateur
        fields = [
            'nom', 'prenom', 'email', 'actif',
            'numero_immatriculation', 'statut', 'equipe',
            'telephone', 'photo'
        ]

    def update(self, instance, validated_data):
        # Mettre à jour l'utilisateur si nécessaire
        user_fields = ['nom', 'prenom', 'email', 'actif']
        user_data = {k: validated_data.pop(k) for k in user_fields if k in validated_data}

        if user_data:
            for attr, value in user_data.items():
                setattr(instance.utilisateur, attr, value)
            instance.utilisateur.save()

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
    """Serializer pour la liste des équipes."""
    chef_equipe_nom = serializers.CharField(
        source='chef_equipe.utilisateur.get_full_name',
        read_only=True
    )
    nombre_membres = serializers.IntegerField(read_only=True)
    statut_operationnel = serializers.CharField(read_only=True)

    class Meta:
        model = Equipe
        fields = [
            'id', 'nom_equipe', 'chef_equipe', 'chef_equipe_nom',
            'specialite', 'actif', 'date_creation',
            'nombre_membres', 'statut_operationnel'
        ]


class EquipeDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour une équipe."""
    chef_equipe_detail = OperateurListSerializer(source='chef_equipe', read_only=True)
    membres = OperateurListSerializer(source='operateurs', many=True, read_only=True)
    nombre_membres = serializers.IntegerField(read_only=True)
    statut_operationnel = serializers.CharField(read_only=True)

    class Meta:
        model = Equipe
        fields = [
            'id', 'nom_equipe', 'chef_equipe', 'chef_equipe_detail',
            'specialite', 'actif', 'date_creation',
            'nombre_membres', 'statut_operationnel', 'membres'
        ]


class EquipeCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'une équipe."""
    membres = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Operateur.objects.all(),
        required=False,
        write_only=True
    )

    class Meta:
        model = Equipe
        fields = ['id', 'nom_equipe', 'chef_equipe', 'specialite', 'actif', 'membres']
        read_only_fields = ['id']

    def validate_chef_equipe(self, value):
        """Vérifie que le chef a la compétence requise."""
        if not value.peut_etre_chef():
            raise serializers.ValidationError(
                "Cet opérateur ne peut pas être chef d'équipe. "
                "Il doit avoir la compétence 'Gestion d'équipe' "
                "avec un niveau Intermédiaire, Expert ou Autorisé."
            )
        return value

    def create(self, validated_data):
        membres = validated_data.pop('membres', [])

        # Créer l'équipe (skip_validation car on a déjà validé)
        equipe = Equipe.objects.create(**validated_data)

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

        # Attribuer le rôle CHEF_EQUIPE au chef
        role_chef, _ = Role.objects.get_or_create(nom_role='CHEF_EQUIPE')
        UtilisateurRole.objects.get_or_create(
            utilisateur=equipe.chef_equipe.utilisateur,
            role=role_chef
        )

        return equipe


class EquipeUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la mise à jour d'une équipe."""

    class Meta:
        model = Equipe
        fields = ['nom_equipe', 'chef_equipe', 'specialite', 'actif']

    def validate_chef_equipe(self, value):
        """Vérifie que le chef a la compétence requise."""
        if not value.peut_etre_chef():
            raise serializers.ValidationError(
                "Cet opérateur ne peut pas être chef d'équipe. "
                "Il doit avoir la compétence 'Gestion d'équipe' "
                "avec un niveau Intermédiaire, Expert ou Autorisé."
            )
        return value


class AffecterMembresSerializer(serializers.Serializer):
    """Serializer pour affecter des membres à une équipe."""
    operateurs = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Operateur.objects.all()
    )

    def update_membres(self, equipe, operateurs):
        """Met à jour les membres d'une équipe."""
        today = timezone.now().date()

        # Retirer les anciens membres
        anciens_membres = equipe.operateurs.all()
        for ancien in anciens_membres:
            if ancien not in operateurs:
                # Fermer l'historique
                HistoriqueEquipeOperateur.objects.filter(
                    operateur=ancien,
                    equipe=equipe,
                    date_fin__isnull=True
                ).update(date_fin=today)

                ancien.equipe = None
                ancien.save()

        # Ajouter les nouveaux membres
        for nouveau in operateurs:
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
# SERIALIZERS ABSENCE
# ==============================================================================

class AbsenceSerializer(serializers.ModelSerializer):
    """Serializer pour les absences."""
    operateur_nom = serializers.CharField(
        source='operateur.utilisateur.get_full_name',
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


class AbsenceValidationSerializer(serializers.Serializer):
    """Serializer pour valider/refuser une absence."""
    action = serializers.ChoiceField(choices=['valider', 'refuser'])
    commentaire = serializers.CharField(required=False, allow_blank=True)

    def update_absence(self, absence, user):
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
        absence.save()

        return absence


# ==============================================================================
# SERIALIZERS HISTORIQUE
# ==============================================================================

class HistoriqueEquipeOperateurSerializer(serializers.ModelSerializer):
    """Serializer pour l'historique des équipes."""
    operateur_nom = serializers.CharField(
        source='operateur.utilisateur.get_full_name',
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
