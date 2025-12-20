from django.contrib.gis.db import models
from django.conf import settings
from api_users.models import Client, Equipe, Utilisateur
from api.models import Site, SousSite
from django.utils import timezone
import datetime

# ==============================================================================
# MODELE TYPE RECLAMATION
# ==============================================================================

class TypeReclamation(models.Model):
    CATEGORIE_CHOICES = [
        ('URGENCE', 'Urgence'),
        ('QUALITE', 'Qualité'),
        ('PLANNING', 'Planning'),
        ('RESSOURCES', 'Ressources'),
        ('AUTRE', 'Autre'),
    ]

    nom_reclamation = models.CharField(max_length=100, verbose_name="Nom de la réclamation")
    code_reclamation = models.CharField(max_length=50, unique=True, verbose_name="Code unique")
    symbole = models.CharField(max_length=50, blank=True, null=True, verbose_name="Symbole")
    categorie = models.CharField(max_length=50, choices=CATEGORIE_CHOICES, verbose_name="Catégorie")
    actif = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Type de réclamation"
        verbose_name_plural = "Types de réclamations"

    def __str__(self):
        return f"{self.nom_reclamation} ({self.categorie})"


# ==============================================================================
# MODELE URGENCE
# ==============================================================================

class Urgence(models.Model):
    NIVEAU_CHOICES = [
        ('FAIBLE', 'Faible'),
        ('MOYENNE', 'Moyenne'),
        ('HAUTE', 'Haute'),
        ('CRITIQUE', 'Critique'),
    ]

    niveau_urgence = models.CharField(max_length=20, choices=NIVEAU_CHOICES, verbose_name="Niveau d'urgence")
    couleur = models.CharField(max_length=20, help_text="Code couleur HEX (ex: #FF0000)", verbose_name="Couleur")
    delai_max_traitement = models.IntegerField(help_text="Délai maximum en heures", verbose_name="Délai max (h)")
    ordre = models.IntegerField(help_text="Ordre de priorité (1-4)", verbose_name="Ordre", default=1)

    class Meta:
        verbose_name = "Urgence"
        verbose_name_plural = "Urgences"
        ordering = ['ordre']

    def __str__(self):
        return f"{self.niveau_urgence} ({self.delai_max_traitement}h)"


# ==============================================================================
# MODELE RECLAMATION
# ==============================================================================

class Reclamation(models.Model):
    STATUT_CHOICES = [
        ('NOUVELLE', 'Nouvelle'),
        ('PRISE_EN_COMPTE', 'Prise en compte'),
        ('EN_COURS', 'En cours'),
        ('RESOLUE', 'Résolue'),
        ('CLOTUREE', 'Clôturée'),
        ('REJETEE', 'Rejetée'),
    ]

    numero_reclamation = models.CharField(max_length=50, unique=True, blank=True, verbose_name="Numéro de réclamation")
    
    type_reclamation = models.ForeignKey(TypeReclamation, on_delete=models.PROTECT, verbose_name="Type")
    urgence = models.ForeignKey(Urgence, on_delete=models.PROTECT, verbose_name="Urgence")

    # Créateur de la réclamation (tout utilisateur peut créer une réclamation)
    createur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reclamations_creees',
        verbose_name="Créateur"
    )

    # Client concerné (optionnel - peut être déduit ou assigné)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Client")

    # Zone correspond à un SousSite dans notre architecture
    zone = models.ForeignKey(SousSite, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Zone")
    # Site parent pour faciliter le filtrage (peut être déduit de la zone)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, null=True, blank=True, verbose_name="Site")
    
    equipe_affectee = models.ForeignKey(Equipe, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Équipe affectée")
    
    localisation = models.GeometryField(srid=4326, blank=True, null=True, verbose_name="Zone affectée")
    
    description = models.TextField(verbose_name="Description du problème")
    justification_rejet = models.TextField(blank=True, null=True, verbose_name="Justification rejet/retard")
    
    date_constatation = models.DateTimeField(verbose_name="Date de constatation")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    
    date_prise_en_compte = models.DateTimeField(null=True, blank=True, verbose_name="Date prise en compte")
    date_debut_traitement = models.DateTimeField(null=True, blank=True, verbose_name="Date début traitement")
    date_resolution = models.DateTimeField(null=True, blank=True, verbose_name="Date résolution")
    
    date_cloture_prevue = models.DateTimeField(null=True, blank=True, verbose_name="Date clôture prévue")
    date_cloture_reelle = models.DateTimeField(null=True, blank=True, verbose_name="Date clôture réelle")
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='NOUVELLE', verbose_name="Statut")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    class Meta:
        verbose_name = "Réclamation"
        verbose_name_plural = "Réclamations"
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.numero_reclamation} - {self.type_reclamation} ({self.statut})"

    def save(self, *args, **kwargs):
        # Génération automatique du numéro de réclamation
        if not self.numero_reclamation:
            annee = timezone.now().year
            # Format: REC-YYYY-XXXX
            last_rec = Reclamation.objects.filter(numero_reclamation__startswith=f"REC-{annee}").order_by('numero_reclamation').last()
            if last_rec:
                try:
                    last_num = int(last_rec.numero_reclamation.split('-')[-1])
                    new_num = last_num + 1
                except ValueError:
                    new_num = 1
            else:
                new_num = 1
            self.numero_reclamation = f"REC-{annee}-{new_num:04d}"
            
        # Calcul date de clôture prévue à la création
        if not self.pk and self.urgence:
            # Si c'est une création
             if not self.date_cloture_prevue:
                 delai_heures = self.urgence.delai_max_traitement
                 self.date_cloture_prevue = timezone.now() + datetime.timedelta(hours=delai_heures)

        # T6.6.3.3 : Détection automatique de la zone (spatial)
        # Si une localisation est fournie mais pas de zone, on essaie de la trouver
        if self.localisation and not self.zone:
            # On cherche le Sous-Site qui contient le point
            found_zone = SousSite.objects.filter(geometrie__intersects=self.localisation).first()
            if found_zone:
                self.zone = found_zone
                # On met à jour le site parent automatiquement
                if not self.site:
                    self.site = found_zone.site
        
        # Validation de cohérence Site/Zone (si les deux sont fournis)
        if self.zone and self.site and self.zone.site != self.site:
             # Si incohérence, on privilégie la Zone qui est plus précise, et on corrige le Site
             self.site = self.zone.site

        super().save(*args, **kwargs)


# ==============================================================================
# MODELE HISTORIQUE RECLAMATION (Timeline)
# ==============================================================================

class HistoriqueReclamation(models.Model):
    reclamation = models.ForeignKey(Reclamation, on_delete=models.CASCADE, related_name='historique', verbose_name="Réclamation")
    statut_precedent = models.CharField(max_length=20, choices=Reclamation.STATUT_CHOICES, null=True, blank=True, verbose_name="Ancien statut")
    statut_nouveau = models.CharField(max_length=20, choices=Reclamation.STATUT_CHOICES, verbose_name="Nouveau statut")
    date_changement = models.DateTimeField(auto_now_add=True, verbose_name="Date du changement")
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Modifié par")
    commentaire = models.TextField(blank=True, null=True, verbose_name="Commentaire/Message")

    class Meta:
        verbose_name = "Historique Réclamation"
        verbose_name_plural = "Historiques Réclamations"
        ordering = ['-date_changement']

    def __str__(self):
        return f"{self.reclamation.numero_reclamation} : {self.statut_precedent} -> {self.statut_nouveau}"


# ==============================================================================
# MODELE SATISFACTION CLIENT (User 6.6.13)
# ==============================================================================

class SatisfactionClient(models.Model):
    reclamation = models.OneToOneField(
        Reclamation, 
        on_delete=models.CASCADE, 
        related_name='satisfaction',
        verbose_name="Réclamation"
    )
    note = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)],
        verbose_name="Note (1-5)"
    )
    commentaire = models.TextField(blank=True, null=True, verbose_name="Commentaire")
    date_evaluation = models.DateTimeField(auto_now_add=True, verbose_name="Date d'évaluation")
    
    class Meta:
        verbose_name = "Satisfaction Client"
        verbose_name_plural = "Satisfactions Clients"
        ordering = ['-date_evaluation']
    
    def __str__(self):
        return f"{self.reclamation.numero_reclamation} - Note: {self.note}/5"
