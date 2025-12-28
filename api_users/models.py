# api_users/models.py
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


# ==============================================================================
# GESTIONNAIRE D'UTILISATEURS PERSONNALISE
# ==============================================================================

class UtilisateurManager(BaseUserManager):
    """
    Gestionnaire personnalisé pour le modèle Utilisateur.
    Permet la création d'utilisateurs avec email comme identifiant principal.
    """

    def create_user(self, email, password=None, **extra_fields):
        """Crée et retourne un utilisateur standard."""
        if not email:
            raise ValueError("L'adresse email est obligatoire")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Crée et retourne un superutilisateur."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Le superutilisateur doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Le superutilisateur doit avoir is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


# ==============================================================================
# ENUMERATIONS
# ==============================================================================




class StatutOperateur(models.TextChoices):
    """Statuts possibles pour un opérateur."""
    ACTIF = 'ACTIF', 'Actif'
    INACTIF = 'INACTIF', 'Inactif'
    EN_CONGE = 'EN_CONGE', 'En congé'


class CategorieCompetence(models.TextChoices):
    """Catégories de compétences."""
    TECHNIQUE = 'TECHNIQUE', 'Techniques et opérationnelles'
    ORGANISATIONNELLE = 'ORGANISATIONNELLE', 'Organisationnelles et humaines'


class NiveauCompetence(models.TextChoices):
    """Niveaux de maîtrise d'une compétence."""
    NON = 'NON', 'Non maîtrisé'
    DEBUTANT = 'DEBUTANT', 'Débutant'
    INTERMEDIAIRE = 'INTERMEDIAIRE', 'Intermédiaire'
    EXPERT = 'EXPERT', 'Expert'


class TypeAbsence(models.TextChoices):
    """Types d'absences possibles."""
    CONGE = 'CONGE', 'Congé'
    MALADIE = 'MALADIE', 'Maladie'
    FORMATION = 'FORMATION', 'Formation'
    AUTRE = 'AUTRE', 'Autre'


class StatutAbsence(models.TextChoices):
    """Statuts possibles pour une absence."""
    DEMANDEE = 'DEMANDEE', 'Demandée'
    VALIDEE = 'VALIDEE', 'Validée'
    REFUSEE = 'REFUSEE', 'Refusée'
    ANNULEE = 'ANNULEE', 'Annulée'


class StatutEquipe(models.TextChoices):
    """Statuts opérationnels d'une équipe."""
    COMPLETE = 'COMPLETE', 'Complète'
    PARTIELLE = 'PARTIELLE', 'Partiellement disponible'
    INDISPONIBLE = 'INDISPONIBLE', 'Non disponible'


# ==============================================================================
# MODELE UTILISATEUR (Base)
# ==============================================================================

class Utilisateur(AbstractBaseUser, PermissionsMixin):
    """
    Modèle utilisateur personnalisé utilisant l'email comme identifiant.

    Entité mère pour tous les types d'utilisateurs du système (Admin, Opérateur, Client).
    Hérite de AbstractBaseUser pour l'authentification Django.
    """
    email = models.EmailField(
        unique=True,
        verbose_name="Email",
        help_text="Adresse email de connexion (unique)"
    )
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    date_creation = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    actif = models.BooleanField(
        default=True,
        verbose_name="Actif",
        help_text="Désactiver plutôt que supprimer (soft delete)"
    )
    derniere_connexion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dernière connexion"
    )

    # Champs requis par Django auth
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UtilisateurManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nom', 'prenom']

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.email})"

    def get_full_name(self):
        return f"{self.prenom} {self.nom}"

    def get_short_name(self):
        return self.prenom

    def save(self, *args, **kwargs):
        """Synchronise is_active avec actif."""
        self.is_active = self.actif
        super().save(*args, **kwargs)


# ==============================================================================
# MODELE ROLE
# ==============================================================================

class Role(models.Model):
    """
    Définit les 3 rôles d'utilisateurs de l'application.

    ⚠️ NOUVEAU MODÈLE (Refactorisation Architecture RH) :
    - Les opérateurs et chefs d'équipe NE sont PAS des utilisateurs
    - Ce sont des données RH gérées dans l'application
    - Seuls ADMIN, SUPERVISEUR et CLIENT peuvent se connecter

    Les rôles définissent les droits et permissions des utilisateurs.
    """
    NOM_CHOICES = [
        ('ADMIN', 'Administrateur'),
        ('SUPERVISEUR', 'Superviseur'),
        ('CLIENT', 'Client'),
    ]

    nom_role = models.CharField(
        max_length=50,
        unique=True,
        choices=NOM_CHOICES,
        verbose_name="Nom du rôle"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )

    class Meta:
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"

    def __str__(self):
        return self.get_nom_role_display()


class UtilisateurRole(models.Model):
    """

    # Table d'association N-N entre Utilisateur et Role.

    Permet à un utilisateur d'avoir plusieurs rôles
    (ex: un opérateur peut aussi être chef d'équipe).
    """
    utilisateur = models.ForeignKey(
        Utilisateur,
        on_delete=models.CASCADE,
        related_name='roles_utilisateur'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='utilisateurs_role'
    )
    date_attribution = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Attribution de rôle"
        verbose_name_plural = "Attributions de rôles"
        unique_together = ['utilisateur', 'role']

    def __str__(self):
        return f"{self.utilisateur} - {self.role}"


# ==============================================================================
# MODELE CLIENT
# ==============================================================================

class Client(models.Model):
    """
    Représente un client (maître d'ouvrage).

    Hérite conceptuellement d'Utilisateur via une relation OneToOne.
    Un client possède des sites d'intervention.
    """
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='client_profile'
    )
    nom_structure = models.CharField(
        max_length=255,
        verbose_name="Nom de la structure",
        help_text="Nom de l'entreprise ou organisation"
    )
    adresse = models.TextField(
        blank=True,
        verbose_name="Adresse complète"
    )
    telephone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Téléphone"
    )
    contact_principal = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Contact principal"
    )
    email_facturation = models.EmailField(
        blank=True,
        verbose_name="Email de facturation"
    )
    logo = models.URLField(
        blank=True,
        null=True,
        verbose_name="Logo",
        help_text="URL du logo de l'organisation"
    )

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"

    def __str__(self):
        return self.nom_structure

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


# ==============================================================================
# MODELE SUPERVISEUR
# ==============================================================================

class Superviseur(models.Model):
    """
    Représente un superviseur (encadrant).

    ⚠️ NOUVEAU MODÈLE (Refactorisation Architecture RH) :
    Le superviseur est un UTILISATEUR qui peut se connecter à l'application.
    Il supervise les équipes, gère le planning et le suivi des interventions,
    mais NE va PAS sur le terrain (contrairement au chef d'équipe qui est un opérateur).

    Différences avec Chef d'Équipe (Operateur) :
    - Superviseur : Utilisateur (se connecte) + gère plusieurs équipes + bureau
    - Chef d'équipe : Opérateur (données RH) + dirige 1 équipe + terrain
    """
    utilisateur = models.OneToOneField(
        Utilisateur,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='superviseur_profile'
    )
    matricule = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Matricule superviseur"
    )
    secteur_geographique = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Secteur géographique",
        help_text="Zone géographique sous sa responsabilité"
    )
    telephone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Téléphone professionnel"
    )
    date_prise_fonction = models.DateField(
        verbose_name="Date de prise de fonction"
    )

    class Meta:
        verbose_name = "Superviseur"
        verbose_name_plural = "Superviseurs"
        ordering = ['utilisateur__nom', 'utilisateur__prenom']

    def __str__(self):
        return f"{self.utilisateur.get_full_name()} (Superviseur - {self.matricule})"

    @property
    def equipes_gerees(self):
        """
        Retourne toutes les équipes gérées par ce superviseur.

        ⚠️ LOGIQUE MÉTIER : Un superviseur gère les équipes affectées aux sites
        qu'il supervise. Cette propriété remplace l'ancienne relation ForeignKey.

        Returns:
            QuerySet[Equipe]: Toutes les équipes affectées aux sites du superviseur
        """
        from api_users.models import Equipe
        return Equipe.objects.filter(site__superviseur=self)

    @property
    def nombre_equipes(self):
        """Retourne le nombre d'équipes gérées par ce superviseur."""
        return self.equipes_gerees.filter(actif=True).count()

    @property
    def nombre_operateurs(self):
        """Retourne le nombre total d'opérateurs sous sa supervision."""
        return self.operateurs_supervises.filter(statut='ACTIF').count()


# ==============================================================================
# MODELE COMPETENCE
# ==============================================================================

class Competence(models.Model):
    """
    Définit les compétences possibles pour les opérateurs.

    Les compétences sont réparties en deux catégories:
    - Techniques et opérationnelles (tondeuse, élagage, etc.)
    - Organisationnelles et humaines (gestion d'équipe, etc.)

    Note: La base doit être pré-remplie avec les compétences standards
    lors de l'initialisation de l'application.
    """
    nom_competence = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nom de la compétence"
    )
    categorie = models.CharField(
        max_length=20,
        choices=CategorieCompetence.choices,
        verbose_name="Catégorie"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    ordre_affichage = models.PositiveIntegerField(
        default=0,
        verbose_name="Ordre d'affichage"
    )

    class Meta:
        verbose_name = "Compétence"
        verbose_name_plural = "Compétences"
        ordering = ['categorie', 'ordre_affichage', 'nom_competence']

    def __str__(self):
        return f"{self.nom_competence} ({self.get_categorie_display()})"


# ==============================================================================
# MODELE EQUIPE
# ==============================================================================

class Equipe(models.Model):
    """
    Représente une équipe d'opérateurs.

    ⚠️ REFACTORISATION (Architecture RH) :
    - Une équipe est affectée à un SITE
    - Le superviseur de l'équipe est automatiquement celui du site (propriété calculée)
    - Un opérateur peut être désigné comme "chef d'équipe" (attribut, pas rôle)
    - Le chef d'équipe travaille sur le terrain avec son équipe

    Règles métier:
    - Une équipe PEUT avoir un chef (opérateur avec compétence "Gestion d'équipe")
    - Un opérateur ne peut être chef que d'UNE SEULE équipe (OneToOne)
    - Une équipe est affectée à un site, son superviseur est celui du site
    """
    nom_equipe = models.CharField(
        max_length=100,
        verbose_name="Nom de l'équipe"
    )

    chef_equipe = models.OneToOneField(
        'Operateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipe_dirigee',
        verbose_name="Chef d'équipe",
        help_text="Opérateur désigné comme chef (doit avoir compétence 'Gestion d\\'équipe')"
    )

    # ⚠️ SUPPRIMÉ : Le superviseur est désormais automatiquement déduit du site
    # superviseur = models.ForeignKey(...) - Voir @property superviseur ci-dessous

    site = models.ForeignKey(
        'api.Site',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipes_affectees',
        verbose_name="Site d'affectation contractuelle",
        help_text="Site auquel l'équipe est affectée de manière contractuelle (affectation de base)"
    )

    actif = models.BooleanField(
        default=True,
        verbose_name="Équipe active"
    )
    date_creation = models.DateField(
        auto_now_add=True,
        verbose_name="Date de création"
    )

    class Meta:
        verbose_name = "Équipe"
        verbose_name_plural = "Équipes"
        ordering = ['nom_equipe']

    def __str__(self):
        return f"{self.nom_equipe} (Chef: {self.chef_equipe})"

    @property
    def nombre_membres(self):
        """Retourne le nombre d'opérateurs dans l'équipe."""
        return self.operateurs.filter(statut=StatutOperateur.ACTIF).count()

    @property
    def superviseur(self):
        """
        Retourne le superviseur de l'équipe, automatiquement déduit du site.

        ⚠️ LOGIQUE MÉTIER : Le superviseur d'une équipe est celui qui supervise
        le site sur lequel l'équipe est affectée.

        Returns:
            Superviseur | None: Le superviseur du site, ou None si pas de site
        """
        return self.site.superviseur if self.site else None

    @property
    def statut_operationnel(self):
        """
        Calcule le statut opérationnel de l'équipe basé sur les absences.

        Returns:
            str: COMPLETE, PARTIELLE ou INDISPONIBLE
        """
        from django.utils import timezone
        today = timezone.now().date()

        membres = self.operateurs.filter(statut=StatutOperateur.ACTIF)
        total = membres.count()

        if total == 0:
            return StatutEquipe.INDISPONIBLE

        # Compte les membres disponibles (sans absence validée aujourd'hui)
        disponibles = 0
        for membre in membres:
            absence_aujourdhui = membre.absences.filter(
                statut=StatutAbsence.VALIDEE,
                date_debut__lte=today,
                date_fin__gte=today
            ).exists()
            if not absence_aujourdhui:
                disponibles += 1

        if disponibles == total:
            return StatutEquipe.COMPLETE
        elif disponibles > 0:
            return StatutEquipe.PARTIELLE
        else:
            return StatutEquipe.INDISPONIBLE

    def clean(self):
        """Valide que le chef a la competence 'Gestion d'équipe'."""
        # Si aucun chef n'est défini, on autorise la création sans chef.
        if self.chef_equipe_id:
            has_gestion = CompetenceOperateur.objects.filter(
                operateur=self.chef_equipe,
                competence__nom_competence="Gestion d'équipe",
                niveau__in=[NiveauCompetence.INTERMEDIAIRE, NiveauCompetence.EXPERT]
            ).exists()

            if not has_gestion:
                raise ValidationError({
                    'chef_equipe': "Le chef d'équipe doit avoir la competence 'Gestion d'équipe' "
                                   "avec un niveau Intermédiaire ou Expert."
                })

    def save(self, *args, **kwargs):
        # Skip validation if chef_equipe is being set for the first time
        # and we want to allow initial setup
        skip_validation = kwargs.pop('skip_validation', False)
        if not skip_validation:
            self.full_clean()
        super().save(*args, **kwargs)


# ==============================================================================
# MODELE OPERATEUR
# ==============================================================================

class Operateur(models.Model):
    """
    Représente un opérateur terrain (jardinier) - DONNÉE RH.

    ⚠️ REFACTORISATION (Architecture RH) :
    - L'opérateur N'EST PAS un utilisateur de l'application
    - Il NE peut PAS se connecter
    - C'est une donnée RH gérée PAR les superviseurs/admins
    - Il travaille sur le terrain (tonte, taille, arrosage, etc.)
    - Un opérateur peut être désigné comme "chef d'équipe" (via Equipe.chef_equipe)

    Différence avec Superviseur :
    - Opérateur : Données RH + terrain + ne se connecte pas
    - Superviseur : Utilisateur + bureau + se connecte
    """
    # ⚠️ CHANGEMENT MAJEUR : Plus de lien avec Utilisateur
    # utilisateur = OneToOneField(...)  ← SUPPRIMÉ

    # Identifiant propre
    id = models.AutoField(primary_key=True)
    # Informations personnelles
    nom = models.CharField(max_length=100, verbose_name="Nom")
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    email = models.EmailField(
        blank=True,
        verbose_name="Email professionnel",
        help_text="Pour communication interne uniquement (n'est PAS un compte de connexion)"
    )

    # Informations RH
    numero_immatriculation = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Matricule",
        help_text="Numéro d'immatriculation unique"
    )
    statut = models.CharField(
        max_length=20,
        choices=StatutOperateur.choices,
        default=StatutOperateur.ACTIF,
        verbose_name="Statut"
    )
    equipe = models.ForeignKey(
        Equipe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operateurs',
        verbose_name="Équipe"
    )
    date_embauche = models.DateField(
        verbose_name="Date d'embauche"
    )
    date_sortie = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de sortie",
        help_text="Date de fin de contrat ou départ"
    )

    # Lien avec le superviseur
    superviseur = models.ForeignKey(
        Superviseur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='operateurs_supervises',
        verbose_name="Superviseur responsable",
        help_text="Superviseur qui gère cet opérateur"
    )

    photo = models.URLField(
        blank=True,
        null=True,
        verbose_name="Photo",
        help_text="URL de la photo de l'opérateur"
    )
    telephone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="Téléphone"
    )
    competences = models.ManyToManyField(
        Competence,
        through='CompetenceOperateur',
        related_name='operateurs',
        verbose_name="Compétences"
    )

    class Meta:
        verbose_name = "Opérateur"
        verbose_name_plural = "Opérateurs"
        ordering = ['nom', 'prenom']

    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.numero_immatriculation})"

    @property
    def nom_complet(self):
        """Retourne le nom complet de l'opérateur."""
        return f"{self.prenom} {self.nom}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @property
    def est_chef_equipe(self):
        """Vérifie si l'opérateur est chef d'une équipe."""
        # Dans la nouvelle architecture, un opérateur ne peut diriger qu'une seule équipe (OneToOne)
        return hasattr(self, 'equipe_dirigee') and self.equipe_dirigee is not None and self.equipe_dirigee.actif

    @property
    def est_disponible(self):
        """Vérifie si l'opérateur est disponible aujourd'hui."""
        from django.utils import timezone
        today = timezone.now().date()

        if self.statut != StatutOperateur.ACTIF:
            return False

        return not self.absences.filter(
            statut=StatutAbsence.VALIDEE,
            date_debut__lte=today,
            date_fin__gte=today
        ).exists()

    def peut_etre_chef(self):
        """Verifie si l'operateur peut etre chef d'equipe."""
        return CompetenceOperateur.objects.filter(
            operateur=self,
            competence__nom_competence="Gestion d'équipe",
            niveau__in=[NiveauCompetence.INTERMEDIAIRE, NiveauCompetence.EXPERT]
        ).exists()


# ==============================================================================
# MODELE COMPETENCE_OPERATEUR (Association)
# ==============================================================================

class CompetenceOperateur(models.Model):
    """
    Table d'association entre Opérateur et Compétence.

    Stocke le niveau de maîtrise de chaque compétence pour chaque opérateur.
    """
    operateur = models.ForeignKey(
        Operateur,
        on_delete=models.CASCADE,
        related_name='competences_operateur'
    )
    competence = models.ForeignKey(
        Competence,
        on_delete=models.CASCADE,
        related_name='operateurs_competence'
    )
    niveau = models.CharField(
        max_length=20,
        choices=NiveauCompetence.choices,
        default=NiveauCompetence.NON,
        verbose_name="Niveau de maîtrise"
    )
    date_acquisition = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date d'acquisition"
    )
    date_modification = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )

    class Meta:
        verbose_name = "Compétence opérateur"
        verbose_name_plural = "Compétences opérateurs"
        unique_together = ['operateur', 'competence']

    def __str__(self):
        return f"{self.operateur} - {self.competence}: {self.get_niveau_display()}"


# ==============================================================================
# MODELE ABSENCE
# ==============================================================================

class Absence(models.Model):
    """
    Gère les absences et congés des opérateurs.

    Une absence validée impacte automatiquement la disponibilité
    de l'opérateur et le statut opérationnel de son équipe.
    """
    operateur = models.ForeignKey(
        Operateur,
        on_delete=models.CASCADE,
        related_name='absences',
        verbose_name="Opérateur"
    )
    type_absence = models.CharField(
        max_length=20,
        choices=TypeAbsence.choices,
        verbose_name="Type d'absence"
    )
    date_debut = models.DateField(
        verbose_name="Date de début"
    )
    date_fin = models.DateField(
        verbose_name="Date de fin"
    )
    statut = models.CharField(
        max_length=20,
        choices=StatutAbsence.choices,
        default=StatutAbsence.DEMANDEE,
        verbose_name="Statut"
    )
    motif = models.TextField(
        blank=True,
        verbose_name="Motif"
    )
    date_demande = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de demande"
    )
    validee_par = models.ForeignKey(
        Utilisateur,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='absences_validees',
        verbose_name="Validée par"
    )
    date_validation = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Date de validation"
    )
    commentaire = models.TextField(
        blank=True,
        verbose_name="Commentaire"
    )

    class Meta:
        verbose_name = "Absence"
        verbose_name_plural = "Absences"
        ordering = ['-date_debut']

    def __str__(self):
        return f"{self.operateur} - {self.get_type_absence_display()} ({self.date_debut} - {self.date_fin})"

    def clean(self):
        """Valide qu'il n'y a pas de chevauchement d'absences."""
        if self.date_debut and self.date_fin:
            if self.date_fin < self.date_debut:
                raise ValidationError({
                    'date_fin': "La date de fin doit être postérieure à la date de début."
                })

            # Vérifie le chevauchement avec d'autres absences
            chevauchement = Absence.objects.filter(
                operateur=self.operateur,
                statut__in=[StatutAbsence.DEMANDEE, StatutAbsence.VALIDEE],
                date_debut__lte=self.date_fin,
                date_fin__gte=self.date_debut
            )

            if self.pk:
                chevauchement = chevauchement.exclude(pk=self.pk)

            if chevauchement.exists():
                raise ValidationError(
                    "Cette période chevauche une autre absence existante."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duree_jours(self):
        """Calcule la durée de l'absence en jours."""
        if self.date_debut and self.date_fin:
            return (self.date_fin - self.date_debut).days + 1
        return 0


# ==============================================================================
# MODELE HISTORIQUE EQUIPE OPERATEUR
# ==============================================================================

class HistoriqueEquipeOperateur(models.Model):
    """
    Historise les affectations des opérateurs aux équipes.

    Permet de tracer l'évolution RH et les changements d'équipe.
    """
    operateur = models.ForeignKey(
        Operateur,
        on_delete=models.CASCADE,
        related_name='historique_equipes'
    )
    equipe = models.ForeignKey(
        Equipe,
        on_delete=models.CASCADE,
        related_name='historique_operateurs'
    )
    date_debut = models.DateField(
        verbose_name="Date d'entrée dans l'équipe"
    )
    date_fin = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de sortie de l'équipe"
    )
    role_dans_equipe = models.CharField(
        max_length=50,
        default='MEMBRE',
        verbose_name="Rôle dans l'équipe"
    )

    class Meta:
        verbose_name = "Historique équipe"
        verbose_name_plural = "Historiques équipes"
        ordering = ['-date_debut']

    def __str__(self):
        fin = self.date_fin or "présent"
        return f"{self.operateur} dans {self.equipe} ({self.date_debut} - {fin})"
