from django.db import models
from api_users.models import Client, Equipe, Operateur
from api.models import Objet
from django.utils import timezone

class TypeTache(models.Model):
    nom_tache = models.CharField(max_length=100, unique=True, verbose_name="Nom de la tâche")
    symbole = models.CharField(max_length=50, blank=True, verbose_name="Symbole")
    description = models.TextField(blank=True, verbose_name="Description")
    productivite_theorique = models.FloatField(null=True, blank=True, verbose_name="Productivité théorique")

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

    id_client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='taches', verbose_name="Client")
    id_type_tache = models.ForeignKey(TypeTache, on_delete=models.PROTECT, related_name='taches', verbose_name="Type de tâche")
    id_equipe = models.ForeignKey(Equipe, on_delete=models.SET_NULL, null=True, blank=True, related_name='taches', verbose_name="Équipe")
    
    date_debut_planifiee = models.DateTimeField(verbose_name="Date début planifiée")
    date_fin_planifiee = models.DateTimeField(verbose_name="Date fin planifiée")
    date_echeance = models.DateField(null=True, blank=True, verbose_name="Date d'échéance")
    
    priorite = models.IntegerField(choices=PRIORITE_CHOICES, default=3, verbose_name="Priorité")
    commentaires = models.TextField(blank=True, verbose_name="Commentaires")
    
    date_affectation = models.DateField(null=True, blank=True, verbose_name="Date d'affectation")
    date_debut_reelle = models.DateTimeField(null=True, blank=True, verbose_name="Date début réelle")
    date_fin_reelle = models.DateTimeField(null=True, blank=True, verbose_name="Date fin réelle")
    duree_reelle_minutes = models.IntegerField(null=True, blank=True, verbose_name="Durée réelle (minutes)")
    
    description_travaux = models.TextField(blank=True, verbose_name="Description des travaux")
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='PLANIFIEE', verbose_name="Statut")
    note_qualite = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Note qualité (1-5)")
    
    parametres_recurrence = models.JSONField(null=True, blank=True, verbose_name="Paramètres récurrence")
    
    # Self-referencing FK for recurrence
    id_recurrence_parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='occurrences', verbose_name="Tâche mère")
    
    notifiee = models.BooleanField(default=False, verbose_name="Notifiée")
    confirmee = models.BooleanField(default=False, verbose_name="Confirmée")
    
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Supprimé le") # Soft delete

    # Many-to-Many relation with Inventory Objects
    objets = models.ManyToManyField(Objet, related_name='taches', blank=True, verbose_name="Objets inventaire")

    class Meta:
        verbose_name = "Tâche"
        verbose_name_plural = "Tâches"
        ordering = ['date_debut_planifiee']

    def __str__(self):
        return f"{self.id_type_tache} - {self.date_debut_planifiee}"
        
    def delete(self, using=None, keep_parents=False):
        """Soft delete implementation"""
        self.deleted_at = timezone.now()
        self.save()

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
