from django.db import models
from django.core.exceptions import ValidationError
from api_users.models import Client, StructureClient, Equipe, Operateur
from api.models import Objet
from django.utils import timezone

# TODO: La fonctionnalité de création de type de tâche côté frontend a été supprimée (bouton "Créer un nouveau type").
# Elle doit être réactivée uniquement si nécessaire, via le backend ou une interface admin dédiée.
# Voir demande utilisateur du 17/12/2025.
class TypeTache(models.Model):
    UNITE_PRODUCTIVITE_CHOICES = [
        ('m2', 'Mètres carrés (m²)'),
        ('ml', 'Mètres linéaires (ml)'),
        ('unite', 'Unités'),
        ('cuvettes', 'Cuvettes'),
        ('arbres', 'Arbres'),
    ]

    nom_tache = models.CharField(max_length=100, unique=True, verbose_name="Nom de la tâche")
    symbole = models.CharField(max_length=50, blank=True, verbose_name="Symbole")
    description = models.TextField(blank=True, verbose_name="Description")
    productivite_theorique = models.FloatField(null=True, blank=True, verbose_name="Productivité théorique")
    unite_productivite = models.CharField(
        max_length=20,
        choices=UNITE_PRODUCTIVITE_CHOICES,
        default='m2',
        blank=True,
        verbose_name="Unité de productivité"
    )

    class Meta:
        verbose_name = "Type de tâche"
        verbose_name_plural = "Types de tâches"
        ordering = ['nom_tache']

    def __str__(self):
        return self.nom_tache

class Tache(models.Model):
    PRIORITE_CHOICES = [
        (1, 'Priorité 1 (Très basse)'),
        (2, 'Priorité 2 (Basse)'),
        (3, 'Priorité 3 (Moyenne)'),
        (4, 'Priorité 4 (Haute)'),
        (5, 'Priorité 5 (Urgent)'),
    ]
    
    STATUT_CHOICES = [
        ('PLANIFIEE', 'Planifiée'),
        ('NON_DEBUTEE', 'Non débutée'),
        ('EN_COURS', 'En cours'),
        ('TERMINEE', 'Terminée'),
        ('ANNULEE', 'Annulée'),
    ]

    ETAT_VALIDATION_CHOICES = [
        ('EN_ATTENTE', 'En attente de validation'),
        ('VALIDEE', 'Validée'),
        ('REJETEE', 'Rejetée'),
    ]

    # Structure cliente pour la tâche
    id_structure_client = models.ForeignKey(
        StructureClient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches',
        verbose_name="Structure cliente"
    )

    # LEGACY: Ancien champ client (à supprimer après migration)
    id_client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches_legacy',
        verbose_name="[LEGACY] Client"
    )

    id_type_tache = models.ForeignKey(TypeTache, on_delete=models.PROTECT, related_name='taches', verbose_name="Type de tâche")

    # Équipe unique (legacy - conservé pour rétrocompatibilité)
    id_equipe = models.ForeignKey(Equipe, on_delete=models.SET_NULL, null=True, blank=True, related_name='taches_legacy', verbose_name="Équipe (legacy)")

    # Multi-équipes (US-PLAN-013)
    equipes = models.ManyToManyField(Equipe, related_name='taches', blank=True, verbose_name="Équipes assignées")
    
    date_debut_planifiee = models.DateTimeField(verbose_name="Date début planifiée")
    date_fin_planifiee = models.DateTimeField(verbose_name="Date fin planifiée")
    date_echeance = models.DateField(null=True, blank=True, verbose_name="Date d'échéance")
    
    priorite = models.IntegerField(choices=PRIORITE_CHOICES, default=3, verbose_name="Priorité")
    commentaires = models.TextField(blank=True, verbose_name="Commentaires")
    
    date_affectation = models.DateField(null=True, blank=True, verbose_name="Date d'affectation")
    date_debut_reelle = models.DateTimeField(null=True, blank=True, verbose_name="Date début réelle")
    date_fin_reelle = models.DateTimeField(null=True, blank=True, verbose_name="Date fin réelle")
    duree_reelle_minutes = models.IntegerField(null=True, blank=True, verbose_name="Durée réelle (minutes)")
    charge_estimee_heures = models.FloatField(null=True, blank=True, verbose_name="Charge estimée (heures)",
        help_text="Calculée automatiquement ou saisie manuellement")
    charge_manuelle = models.BooleanField(default=False, verbose_name="Charge manuelle",
        help_text="Si True, la charge ne sera pas recalculée automatiquement")

    description_travaux = models.TextField(blank=True, verbose_name="Description des travaux")
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='PLANIFIEE', verbose_name="Statut")
    note_qualite = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Note qualité (1-5)")

    # Validation par l'administrateur
    etat_validation = models.CharField(
        max_length=20,
        choices=ETAT_VALIDATION_CHOICES,
        default='EN_ATTENTE',
        verbose_name="État de validation"
    )
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    validee_par = models.ForeignKey(
        'api_users.Utilisateur',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches_validees',
        verbose_name="Validée par"
    )
    commentaire_validation = models.TextField(blank=True, verbose_name="Commentaire de validation")
    
    parametres_recurrence = models.JSONField(null=True, blank=True, verbose_name="Paramètres récurrence")
    
    # Self-referencing FK for recurrence
    id_recurrence_parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='occurrences', verbose_name="Tâche mère")
    
    notifiee = models.BooleanField(default=False, verbose_name="Notifiée")
    confirmee = models.BooleanField(default=False, verbose_name="Confirmée")
    
    # Lien avec Réclamation (MCD Entité 19 / Note 54)
    reclamation = models.ForeignKey(
        'api_reclamations.Reclamation',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='taches_correctives',
        verbose_name="Réclamation liée"
    )
    
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Supprimé le") # Soft delete

    # Many-to-Many relation with Inventory Objects
    objets = models.ManyToManyField(Objet, related_name='taches', blank=True, verbose_name="Objets inventaire")

    class Meta:
        verbose_name = "Tâche"
        verbose_name_plural = "Tâches"
        ordering = ['date_debut_planifiee']

    def __str__(self):
        return f"{self.id_type_tache} - {self.date_debut_planifiee}"

    def clean(self):
        """Validation métier de la tâche"""
        super().clean()

        # RÈGLE D'OR: Une tâche doit avoir lieu sur le MÊME jour calendaire
        if self.date_debut_planifiee and self.date_fin_planifiee:
            if self.date_debut_planifiee.date() != self.date_fin_planifiee.date():
                raise ValidationError({
                    'date_fin_planifiee':
                        f"Une tâche doit obligatoirement avoir lieu sur le même jour calendaire. "
                        f"Début: {self.date_debut_planifiee.date().strftime('%d/%m/%Y')}, "
                        f"Fin: {self.date_fin_planifiee.date().strftime('%d/%m/%Y')}. "
                        f"Pour planifier sur plusieurs jours, créez plusieurs tâches ou utilisez la récurrence."
                })

            if self.date_fin_planifiee < self.date_debut_planifiee:
                raise ValidationError({
                    'date_fin_planifiee': "La date de fin ne peut pas être antérieure à la date de début."
                })

    def delete(self, using=None, keep_parents=False):
        """Soft delete implementation"""
        self.deleted_at = timezone.now()
        self.save()

class RatioProductivite(models.Model):
    """
    Matrice de productivité: ratio par combinaison (TypeTache, type_objet).
    Le ratio représente le nombre d'unités traitables par heure.
    """
    UNITE_CHOICES = [
        ('m2', 'Mètres carrés'),
        ('ml', 'Mètres linéaires'),
        ('unite', 'Unité'),
    ]

    id_type_tache = models.ForeignKey(
        TypeTache,
        on_delete=models.CASCADE,
        related_name='ratios_productivite',
        verbose_name="Type de tâche"
    )
    type_objet = models.CharField(
        max_length=50,
        verbose_name="Type d'objet",
        help_text="Nom de la classe (Arbre, Gazon, Palmier, etc.)"
    )
    unite_mesure = models.CharField(
        max_length=10,
        choices=UNITE_CHOICES,
        default='unite',
        verbose_name="Unité de mesure"
    )
    ratio = models.FloatField(
        verbose_name="Ratio (unités/heure)",
        help_text="Nombre d'unités traitables par heure"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description/Notes"
    )
    actif = models.BooleanField(
        default=True,
        verbose_name="Actif"
    )

    class Meta:
        verbose_name = "Ratio de productivité"
        verbose_name_plural = "Ratios de productivité"
        unique_together = ['id_type_tache', 'type_objet']
        ordering = ['id_type_tache', 'type_objet']

    def __str__(self):
        return f"{self.id_type_tache.nom_tache} - {self.type_objet}: {self.ratio} {self.unite_mesure}/h"


class ParticipationTache(models.Model):
    ROLE_CHOICES = [
        ('CHEF', 'Chef d\'équipe'),
        ('MEMBRE', 'Membre'),
    ]

    id_tache = models.ForeignKey(Tache, on_delete=models.CASCADE, related_name='participations')
    id_operateur = models.ForeignKey(Operateur, on_delete=models.CASCADE, related_name='participations_tache')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBRE', verbose_name="Rôle")
    heures_travaillees = models.FloatField(default=0.0, verbose_name="Heures travaillées")
    realisation = models.TextField(blank=True, verbose_name="Réalisation")
    
    class Meta:
        verbose_name = "Participation tâche"
        verbose_name_plural = "Participations tâches"
        unique_together = ['id_tache', 'id_operateur']
        
    def __str__(self):
        return f"{self.id_operateur} - {self.id_tache} ({self.get_role_display()})"
